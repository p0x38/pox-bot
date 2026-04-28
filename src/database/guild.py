from datetime import datetime

import orjson
from pytz import UTC

from src.database import PostgreSQLDatabase
from src.models import ServerFeatureEntry
from src.models import GuildConfig
from src.models import ServerFeatureType
from src.utils import Cache
from logger import logger

class GuildSettingsDatabase(PostgreSQLDatabase):
    def __init__(self, dsn: str):
        super().__init__(dsn)
        self._cache = Cache(ttl=500)
    
    async def on_load(self):
        await self.execute_sql_file("resources/sqls/guild_settings.sql")
        logger.info("[GuildSettingsDatabase] Table verified.")
    
    async def get_config(self, guild_id: int) -> GuildConfig:
        cached = self._cache.get(guild_id)
        if cached:
            return cached
        
        if self.pool:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT config FROM guild_settings WHERE guild_id = $1", guild_id)
                if row:
                    data = orjson.loads(row['config'])
                    config = GuildConfig.from_dict(data)
                else:
                    config = GuildConfig()
                
                self._cache.set(guild_id, config)
                return config
        return GuildConfig()
    
    async def update_config(self, guild_id: int, config: GuildConfig):
        self._cache.set(guild_id, config)
        
        if self.pool:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO guild_settings (guild_id, config)
                    VALUES ($1, $2::jsonb)
                    ON CONFLICT (guild_id) DO UPDATE SET config = EXCLUDED.config
                """, guild_id, orjson.dumps(config.to_dict()))
                
                logger.debug(f"[SettingsDatabase] Updated config for guild {guild_id}")
    
    async def get_feature(self, guild_id: int, feature: ServerFeatureType) -> bool:
        config = await self.get_config(guild_id)
        
        for entry in config.features:
            if entry.name == feature.value:
                return entry.enabled
        return False
    
    async def set_feature(self, guild_id: int, feature: ServerFeatureType, state: bool, user_id: int):
        config = await self.get_config(guild_id)
        
        found = False
        for entry in config.features:
            if entry.name == feature.value:
                entry.enabled = state
                entry.updated_by = user_id
                entry.updated_at = datetime.now(UTC).timestamp()
                found = True
                break
        
        if not found:
            config.features.append(ServerFeatureEntry(
                name=feature.value,
                enabled=state,
                updated_by=user_id
            ))
        
        await self.update_config(guild_id, config)