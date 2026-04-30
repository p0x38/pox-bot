from typing import TypeVar

import orjson

from src.database import PostgreSQLDatabase
from src.models import BaseConfigData, GuildConfigV2
from src.utils import Cache
from logger import logger
from datetime import datetime
from pytz import UTC

T = TypeVar("T", bound=BaseConfigData)

class GuildSettingsDatabaseV2(PostgreSQLDatabase):
    def __init__(self, dsn: str):
        super().__init__(dsn)
        self._cache = Cache(ttl=500)
    
    async def on_load(self):
        await self.run_migrations("resources/migrations")
        logger.info("[GuildSettingsDatabaseV2] Migration suite completed.")
    
    async def get_config(self, guild_id: int) -> GuildConfigV2:
        if not self.pool:
            raise ConnectionAbortedError("SQL Connection not available")
        
        cached = self._cache.get(guild_id)
        if cached:
            return cached
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT config FROM guild_settings WHERE guild_id = $1", guild_id)
            if row:
                data = orjson.loads(row['config'])
                config = GuildConfigV2.from_dict(data)
            else:
                config = GuildConfigV2()
            
            self._cache.set(guild_id, config)
            return config
    
    async def update_config(self, guild_id: int, config: GuildConfigV2):
        if not self.pool:
            raise ConnectionAbortedError("SQL Connection not available")
        
        config_json = orjson.dumps(config.to_dict()).decode('utf-8')
        
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO guild_settings (guild_id, config)
                VALUES ($1, $2::jsonb)
                ON CONFLICT (guild_id) DO UPDATE SET config = EXCLUDED.config
            """, guild_id, config_json)
        
            self._cache.set(guild_id, config)
            logger.debug(f"[SettingsDatabase] Updated config for guild {guild_id}")
    
    async def toggle_feature(self, guild_id: int, feature_key: str, state: bool, user_id: int | None = None):
        config = await self.get_config(guild_id)
        
        feature = config.features.get(feature_key)
        if feature:
            feature.enabled = state
            feature.last_executor = user_id if user_id else None
            feature.last_execution = datetime.now(UTC).timestamp()
            
            await self.update_config(guild_id, config)
            logger.info(f"[{guild_id}] Feature '{feature_key}' set to {state} by {user_id}")
            return True
        return False
    
    async def get_feature(self, guild_id: int, feature_key: str, cast_to: type[T]) -> T | None:
        config = await self.get_config(guild_id)
        feature = config.features.get(feature_key)
        
        if isinstance(feature, cast_to):
            return feature
        return None
    
    async def log_execution(self, guild_id: int, feature_key: str, executor_id: int):
        config = await self.get_config(guild_id)
        feature = config.features.get(feature_key)
        
        if feature:
            feature.last_execution = datetime.now(UTC).timestamp()
            feature.last_executor = executor_id
            await self.update_config(guild_id, config)
    
    async def create_ticket_record(self, channel_id: int, user_id: int, guild_id: int):
        if not self.pool:
            raise ConnectionAbortedError("SQL Pool not available")
        
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO active_tickets (channel_id, user_id, guild_id)
                VALUES ($1, $2, $3)
            """, channel_id, user_id, guild_id)
        
    async def get_ticket_owner(self, channel_id: int) -> int | None:
        if not self.pool:
            raise ConnectionAbortedError("SQL Pool not available")
        
        async with self.pool.acquire() as conn:
            return await conn.fetchval
    
    async def find_random_partner(self, requester_guild_id: int) -> int | None:
        if not self.pool:
            return None
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT guild_id FROM guild_settings
                WHERE (config->'features'->'userphone'->>'status')::int = 1
                AND guild_id != $1
                LIMIT 1
            """, requester_guild_id)
            
            return row['guild_id'] if row else None