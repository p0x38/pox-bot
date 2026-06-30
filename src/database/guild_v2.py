from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from src.bases import BaseDatabase
from src.models.guild_settings_v2 import GuildConfigV2
from src.models.guild_settings_v2_orm import ActiveTicket, GuildSettings
from src.utils.cache import Cache


class GuildSettingsDatabase(BaseDatabase):
    def __init__(self, dsn: str):
        super().__init__(dsn)
        self._cache = Cache(ttl=500)

    async def get_config(self, guild_id: int) -> GuildConfigV2:
        async with self.async_session() as session:
            result = await session.get(GuildSettings, guild_id)
            return result.config if result else GuildConfigV2()

    async def update_config(self, guild_id: int, config: GuildConfigV2):
        async with self.async_session() as session, session.begin():
            db_record = await session.get(GuildSettings, guild_id)

            if db_record:
                db_record.config = config

                flag_modified(db_record, "config")
            else:
                db_record = GuildSettings(guild_id=guild_id, config=config)
                session.add(db_record)

        self._cache.set(guild_id, config)

    async def create_ticket_record(self, channel_id: int, user_id: int, guild_id: int):
        async with self.async_session() as session, session.begin():
            session.add(ActiveTicket(channel_id=channel_id, user_id=user_id, guild_id=guild_id))

    async def find_random_partner(self, requester_guild_id: int) -> int | None:
        async with self.async_session() as session:
            stmt = select(GuildSettings.guild_id).where(
                GuildSettings.guild_id != requester_guild_id,
                GuildSettings.config['features']['userphone']['status'].as_integer() == 1
            ).limit(1)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
