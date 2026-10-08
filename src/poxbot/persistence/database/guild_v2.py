from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import func, select, update
from sqlalchemy.orm.attributes import flag_modified

from ...shared.bases import BaseDatabase
from ...shared.bases.base_orm_model import Base
from ...shared.utils import Cache
from ..models.global_chat_moderation_orm import GlobalChatModerationCase
from ..models.guild_settings_v2 import GuildConfigV2
from ..models.guild_settings_v2_orm import ActiveTicket, GuildSettings

if TYPE_CHECKING:
    from ...application.bot import PoxBot


class GuildSettingsDatabase(BaseDatabase):
    def __init__(self, bot: 'PoxBot', dsn: str):
        super().__init__(bot, dsn)
        self._cache = Cache(ttl=500)

    async def on_load(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.logger.debug('Initialized tables')

    async def get_config(self, guild_id: int) -> GuildConfigV2:
        async with self.async_session() as session, session.begin():
            result = await session.get(GuildSettings, guild_id)
            return result.config if result else GuildConfigV2()

    async def update_config(self, guild_id: int, config: GuildConfigV2):
        async with self.async_session() as session, session.begin():
            db_record = await session.get(GuildSettings, guild_id)

            if db_record:
                db_record.config = config

                flag_modified(db_record, 'config')
            else:
                db_record = GuildSettings(guild_id=guild_id, config=config)
                session.add(db_record)

        self._cache.set(guild_id, config)

    async def create_ticket_record(self, channel_id: int, user_id: int, guild_id: int):
        async with self.async_session() as session, session.begin():
            session.add(
                ActiveTicket(channel_id=channel_id, user_id=user_id, guild_id=guild_id),
            )

    async def create_global_chat_moderation_case(
        self,
        *,
        message_id: int,
        guild_id: int,
        channel_id: int,
        author_id: int,
        reason_codes: list[str],
        message_fingerprint: str,
    ) -> None:
        async with self.async_session() as session, session.begin():
            if await session.get(GlobalChatModerationCase, message_id):
                return
            session.add(
                GlobalChatModerationCase(
                    message_id=message_id,
                    guild_id=guild_id,
                    channel_id=channel_id,
                    author_id=author_id,
                    reason_codes=reason_codes,
                    message_fingerprint=message_fingerprint,
                ),
            )

    async def get_pending_global_chat_moderation_cases(
        self,
        guild_id: int,
        limit: int = 10,
    ) -> list[GlobalChatModerationCase]:
        async with self.async_session() as session:
            statement = (
                select(GlobalChatModerationCase)
                .where(
                    GlobalChatModerationCase.guild_id == guild_id,
                    GlobalChatModerationCase.status == 'pending',
                )
                .order_by(GlobalChatModerationCase.created_at)
                .limit(limit)
            )
            result = await session.execute(statement)
            return list(result.scalars())

    async def get_global_chat_moderation_case(
        self,
        guild_id: int,
        message_id: int,
    ) -> GlobalChatModerationCase | None:
        async with self.async_session() as session:
            case = await session.get(GlobalChatModerationCase, message_id)
            if case is None or case.guild_id != guild_id:
                return None
            return case

    async def resolve_global_chat_moderation_case(
        self,
        *,
        guild_id: int,
        message_id: int,
        status: str,
        reviewer_id: int,
    ) -> bool:
        if status not in {'approved', 'denied', 'stale'}:
            raise ValueError(f'Invalid moderation case status: {status}')

        async with self.async_session() as session, session.begin():
            statement = (
                update(GlobalChatModerationCase)
                .where(
                    GlobalChatModerationCase.guild_id == guild_id,
                    GlobalChatModerationCase.message_id == message_id,
                    GlobalChatModerationCase.status == 'pending',
                )
                .values(
                    status=status,
                    reviewer_id=reviewer_id,
                    reviewed_at=datetime.now(UTC),
                )
                .returning(GlobalChatModerationCase.message_id)
            )
            result = await session.execute(statement)
            return result.scalar_one_or_none() is not None

    async def find_random_partner(self, requester_guild_id: int) -> int | None:
        async with self.async_session() as session, session.begin():
            stmt = select(GuildSettings.guild_id).where(
                GuildSettings.guild_id != requester_guild_id,
            )

            if 'sqlite' in self.engine.url.drivername:
                stmt = stmt.where(
                    func.json_extract(
                        GuildSettings.config, '$.features.userphone.status'
                    )
                    == 1,
                )
            else:
                stmt = stmt.where(
                    GuildSettings.config['features']['userphone']['status'].as_integer()
                    == 1,
                )

            stmt = stmt.limit(1)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
