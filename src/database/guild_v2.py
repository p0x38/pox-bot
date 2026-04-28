from typing import Any

import orjson

from src.database import PostgreSQLDatabase
from src.models import GuildConfigV2
from src.utils import Cache
from logger import logger

class GuildSettingsDatabaseV2(PostgreSQLDatabase):
    def __init__(self, dsn: str):
        super().__init__(dsn)
        self._cache = Cache(ttl=500)
    
    async def on_load(self):
        await self.execute_sql_file("resources/sqls/guild_settings.sql")
        logger.info("[GuildSettingsDatabase] Table verified.")
    
    async def get_config(self, guild_id: int) -> GuildConfigV2:
        cached = self._cache.get(guild_id)
        if cached:
            return cached
        
        if self.pool:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT config FROM guild_settings WHERE guild_id = $1", guild_id)
                if row:
                    data = orjson.loads(row['config'])
                    config = GuildConfigV2.from_dict(data)
                else:
                    config = GuildConfigV2()
                
                self._cache.set(guild_id, config)
                return config
        return GuildConfigV2()
    
    async def update_config(self, guild_id: int, config: GuildConfigV2):
        self._cache.set(guild_id, config)
        
        if self.pool:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO guild_settings (guild_id, config)
                    VALUES ($1, $2::jsonb)
                    ON CONFLICT (guild_id) DO UPDATE SET config = EXCLUDED.config
                """, guild_id, orjson.dumps(config.to_dict()))
                
                logger.debug(f"[SettingsDatabase] Updated config for guild {guild_id}")
    
    async def update_feature(self, guild_id: int, feature_key: str, data_obj: Any):
        config = await self.get_config(guild_id)
        config.features[feature_key] = data_obj
        
        if not self.pool:
            return
        
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO guild_settings (guild_id, config)
                VALUES ($1, $2::jsonb)
                ON CONFLICT (guild_id) DO UPDATE SET config = EXCLUDED.config
            """, guild_id, orjson.dumps(config.to_dict()))