from datetime import date, datetime
from typing import TYPE_CHECKING

from discord import Guild
from pytz import UTC
from sqlalchemy import delete, desc, extract, func, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from ...shared.bases import BaseDatabase
from ...shared.bases.base_orm_model import Base
from ..models.stats_orm import DailyUserActivity, MessageCache, UserStatistics

if TYPE_CHECKING:
    from ...application.bot import PoxBot


class StatisticsDatabase(BaseDatabase):
    def __init__(self, bot: 'PoxBot', dsn: str):
        super().__init__(bot, dsn)

    async def on_load(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.logger.debug('Initialized tables')

    async def add_xp(self, user_id: int, count: int, guild_id: int = 0):
        activity_date = datetime.now(UTC).date()

        async with self.async_session() as session, session.begin():
            user = await session.get(UserStatistics, user_id)

            if not user:
                user = UserStatistics(
                    user_id=user_id,
                    xp=0,
                    level=0,
                    total_messages=0,
                )

            if user.xp is None:
                user.xp = 0
            if user.level is None:
                user.level = 0
            if user.total_messages is None:
                user.total_messages = 0

            old_level = user.level

            user.xp += count
            user.total_messages += 1
            user.level = int(user.xp**0.25)

            session.add(user)

            values = {
                'user_id': user_id,
                'guild_id': guild_id,
                'activity_date': activity_date,
                'message_count': 1,
                'character_count': count,
                'xp_gained': count,
            }

            dialect = self.engine.dialect.name

            if dialect == 'sqlite':
                statement = sqlite_insert(DailyUserActivity).values(**values)
            elif dialect == 'postgresql':
                statement = postgres_insert(DailyUserActivity).values(**values)
            else:
                key = (user_id, guild_id, activity_date)
                daily = await session.get(DailyUserActivity, key)

                if daily is None:
                    session.add(DailyUserActivity(**values))
                else:
                    daily.message_count += 1
                    daily.character_count += count
                    daily.xp_gained += count

                return {
                    'leveled_up': user.level > old_level,
                    'new_level': user.level,
                }

            statement = statement.on_conflict_do_update(
                index_elements=[
                    DailyUserActivity.user_id,
                    DailyUserActivity.guild_id,
                    DailyUserActivity.activity_date,
                ],
                set_={
                    'message_count': (
                        DailyUserActivity.message_count
                        + statement.excluded.message_count
                    ),
                    'character_count': (
                        DailyUserActivity.character_count
                        + statement.excluded.character_count
                    ),
                    'xp_gained': (
                        DailyUserActivity.xp_gained + statement.excluded.xp_gained
                    ),
                },
            )

            await session.execute(statement)

            return {
                'leveled_up': user.level > old_level,
                'new_level': user.level,
            }

    async def get_user_statistics(self, user_id: int) -> UserStatistics | None:
        async with self.async_session() as session, session.begin():
            return await session.get(UserStatistics, user_id)

    async def get_leaderboard(self, sort_by: str = 'xp', limit: int = 10):
        async with self.async_session() as session, session.begin():
            col = getattr(UserStatistics, sort_by, UserStatistics.xp)
            stmt = select(UserStatistics).order_by(desc(col)).limit(limit)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_guild_leaderboard(
        self,
        guild: Guild,
        sort_by: str = 'xp',
        limit: int = 10,
    ):
        async with self.async_session() as session, session.begin():
            col = getattr(UserStatistics, sort_by, UserStatistics.xp)
            stmt = select(UserStatistics).order_by(desc(col)).limit(limit)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def cache_message(self, **kwargs):
        async with self.async_session() as session, session.begin():
            await session.merge(MessageCache(**kwargs))

            subquery = (
                select(MessageCache.message_id)
                .where(MessageCache.channel_id == kwargs['channel_id'])
                .order_by(MessageCache.message_id.desc())
                .limit(15000)
                .scalar_subquery()
            )

            await session.execute(
                delete(MessageCache).where(
                    MessageCache.channel_id == kwargs['channel_id'],
                    MessageCache.message_id.notin_(subquery),
                ),
            )

    async def get_cached_messages(self, channel_id: int, limit: int) -> list[str]:
        async with self.async_session() as session, session.begin():
            result = await session.execute(
                select(MessageCache.content)
                .where(MessageCache.channel_id == channel_id)
                .order_by(MessageCache.message_id.desc())
                .limit(limit),
            )
            return list(result.scalars().all())

    async def get_active_pattern(
        self,
        channel_id: int,
        target_user_id: int | None = None,
    ):
        async with self.async_session() as session, session.begin():
            if 'sqlite' in self.engine.url.drivername:
                hour_expr = func.strftime('%H', MessageCache.created_at)
            else:
                hour_expr = extract('hour', MessageCache.created_at)

            stmt = select(
                hour_expr.label('hour'),
                func.count().label('count'),
            ).where(MessageCache.channel_id == channel_id)

            if target_user_id:
                stmt = stmt.where(MessageCache.author_id == target_user_id)

            stmt = stmt.group_by(hour_expr).order_by(hour_expr)
            result = await session.execute(stmt)
            return result.mappings().all()

    async def get_daily_activity(
        self,
        start_date: date,
        end_date: date,
        guild_id: int | None = None,
    ):
        conditions = [
            DailyUserActivity.activity_date >= start_date,
            DailyUserActivity.activity_date <= end_date,
        ]

        if guild_id is not None:
            conditions.append(DailyUserActivity.guild_id == guild_id)

        statement = (
            select(
                DailyUserActivity.activity_date.label('date'),
                func.sum(DailyUserActivity.message_count).label('messages'),
                func.sum(DailyUserActivity.character_count).label('characters'),
                func.sum(DailyUserActivity.xp_gained).label('xp'),
            )
            .where(*conditions)
            .group_by(DailyUserActivity.activity_date)
            .order_by(DailyUserActivity.activity_date)
        )

        async with self.async_session() as session:
            result = await session.execute(statement)
            return [dict(row) for row in result.mappings().all()]
