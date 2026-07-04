from typing import TYPE_CHECKING

from sqlalchemy import delete, desc, extract, func, select

from ...shared.bases import BaseDatabase
from ..models.stats_orm import MessageCache, UserStatistics

if TYPE_CHECKING:
    from ...application.bot import PoxBot


class StatisticsDatabase(BaseDatabase):
    def __init__(self, bot: 'PoxBot', dsn: str):
        super().__init__(bot, dsn)

    async def add_xp(self, user_id: int, count: int):
        async with self.async_session() as session, session.begin():
            user = await session.get(UserStatistics, user_id) or UserStatistics(
                user_id=user_id,
            )

            old_level = user.level
            user.xp += count
            user.total_messages += 1
            user.level = int(user.xp**0.25)

            session.add(user)
            return {'leveled_up': user.level > old_level, 'new_level': user.level}

    async def get_user_statistics(self, user_id: int) -> UserStatistics | None:
        async with self.async_session() as session:
            return await session.get(UserStatistics, user_id)

    async def get_leaderboard(self, sort_by: str = 'xp', limit: int = 10):
        async with self.async_session() as session:
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
        async with self.async_session() as session:
            result = await session.execute(
                select(MessageCache.content)
                .where(MessageCache.channel_id == channel_id)
                .order_by(MessageCache.message_id.desc())
                .limit(limit),
            )
            return list(result.scalars().all())

    async def get_active_pattern(
        self, channel_id: int, target_user_id: int | None = None,
    ):
        async with self.async_session() as session:
            stmt = select(
                extract('hour', MessageCache.created_at).label('hour'),
                func.count().label('count'),
            ).where(MessageCache.channel_id == channel_id)

            if target_user_id:
                stmt = stmt.where(MessageCache.author_id == target_user_id)

            stmt = stmt.group_by('hour').order_by('hour')
            result = await session.execute(stmt)
            return result.mappings().all()
