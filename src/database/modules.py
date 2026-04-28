from datetime import datetime
import json
import time
from typing import Dict, List, Optional

from discord import Interaction
from pytz import UTC

from src.utils.cache import Cache
from .base import PostgreSQLDatabase
from src.models import EconomyData, GuildConfig, ServerFeatureEntry, ServerFeatureType, SettingsData
import orjson
from src.translator import translator_instance
from logger import logger

class SettingsDatabase(PostgreSQLDatabase):
    def __init__(self, dsn: str):
        super().__init__(dsn)
        self.settings_cache = Cache(ttl=600)
    
    async def on_load(self):
        if self.pool:
            async with self.pool.acquire() as conn:
                await self.execute_sql_file("resources/sqls/settings.sql")
            logger.info("[SettingsDatabase] Tables verified.")
    
    async def pre_close(self):
        logger.debug("[SettingsDatabase] Clearing cache before shutdown...")
        self.settings_cache.clear()
    
    async def get_locale(self, interaction: Interaction) -> str:
        user_id = interaction.user.id

        cached_settings = self.settings_cache.get(user_id)
        if cached_settings and cached_settings.locale:
            return translator_instance._normalize_locale(cached_settings.locale)
        
        settings = await self.get_settings(user_id)
        if settings.locale:
            self.settings_cache.set(user_id, settings)
            return translator_instance._normalize_locale(settings.locale)
        
        return translator_instance._normalize_locale(interaction.locale)
    
    async def get_settings(self, user_id: int, use_cache: bool = True) -> SettingsData:
        if use_cache:
            cached_val = self.settings_cache.get(user_id)
            if cached_val:
                return cached_val
        
        if self.pool:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT data FROM user_preferences WHERE user_id = $1", user_id)
                if row:
                    raw_data = row['data']
                    parsed_data = orjson.loads(raw_data) if isinstance(raw_data, (str, bytes)) else raw_data

                    loc = parsed_data.get('locale')
                    settings = SettingsData.from_dict(parsed_data)
                else:
                    settings = SettingsData()
                
                self.settings_cache.set(user_id, settings)

                print("AFTER LOAD:", settings.locale, type(settings.locale))
                return settings
        else:
            return SettingsData()
    
    async def set_settings(self, user_id: int, settings: SettingsData):
        print("BEFORE SAVE", settings.locale, type(settings.locale))
        
        if isinstance(settings.locale, list):
            settings.locale = settings.locale[0] if settings.locale else 'en'
        
        self.settings_cache.set(user_id, settings)
        
        if self.pool:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO user_preferences (user_id, data)
                    VALUES ($1, $2::jsonb)
                    ON CONFLICT (user_id) DO UPDATE SET data = EXCLUDED.data
                """, user_id, json.dumps(settings.to_dict()))

class StatsDatabase(PostgreSQLDatabase):
    async def on_load(self):
        await self.execute_sql_file("resources/sqls/user_stats.sql")
        logger.info("[UserStatsDatabase] Tables verified.")
    
    async def add_xp(self, user_id: int, count: int):
        if self.pool:
            query = """
            INSERT INTO user_stats (user_id, xp, total_messages, level)
            VALUES ($1, $2, 1, 1)
            ON CONFLICT (user_id) DO UPDATE SET
                xp = user_stats.xp + $2,
                total_messages = user_stats.total_messages + 1,
                level = CASE
                    WHEN floor(pow(user_stats.xp + $2, 0.25)) > user_stats.level
                    THEN floor(pow(user_stats.xp + $2, 0.25))
                    ELSE user_stats.level
                END
            RETURNING
                (floor(pow(user_stats.xp + $2, 0.25)) > user_stats.level) AS leveled_up,
                level AS new_level;
            """
            return await self.pool.fetchrow(query, user_id, count)
        return False
    
    async def get_leaderboard(self, sort_by: str = "xp", limit: int = 10):
        if self.pool:
            query = f"SELECT user_id, xp, level FROM user_stats ORDER BY {sort_by} DESC LIMIT $1"
            return await self.pool.fetch(query, limit)

class EconomyDatabase(PostgreSQLDatabase):
    def __init__(self, dsn: str):
        super().__init__(dsn)
        self._cache = Cache(ttl=300)
    
    async def on_load(self):
        await self.execute_sql_file("resources/sqls/economy.sql")
    
    async def post_close(self):
        logger.info("[EconomyDatabase] Cleanup complete.")
    
    async def pre_close(self):
        logger.info("[EconomyDatabase] Clearing caches...")
        self._cache.clear()
    
    async def get_user(self, user_id: int) -> EconomyData:
        cached = self._cache.get(user_id)
        if cached: return cached

        if self.pool:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT * FROM economy_users WHERE user_id = $1", user_id)
                user_obj = EconomyData.from_row(row)
                if not row:
                    user_obj.user_id = user_id

                self._cache.set(user_id, user_obj)
                return user_obj
        return EconomyData(user_id=user_id)
    
    async def save_user(self, user: EconomyData):
        self._cache.set(user.user_id, user)
        if self.pool:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO economy_users (user_id, wallet, bank, last_daily, last_work)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (user_id) DO UPDATE SET
                        wallet = EXCLUDED.wallet,
                        bank = EXCLUDED.bank,
                        last_daily = EXCLUDED.last_daily
                        last_work = EXCLUDED.last_work
                """, user.user_id, user.wallet, user.bank, user.last_daily, user.last_work)
    
    async def get_shop_items(self) -> List[dict]:
        if self.pool:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("SELECT * FROM economy_items WHERE buy_price IS NOT NULL")
                return [dict(r) for r in rows]
        return []
    
    async def get_item(self, item_id: str) -> Optional[dict]:
        if self.pool:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT * FROM economy_items WHERE id = $1", item_id)
                return dict(row) if row else None
        return None
    
    async def modify_inventory(self, user_id: int, item_id: str, amount: int):
        if self.pool:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO economy_inventory (user_id, item_id, quantity)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (user_id, item_id) DO UPDATE
                    SET quantity = economy_inventory.quantity + EXCLUDED.quantity
                """, user_id, item_id, amount)

                await conn.execute("DELETE FROM economy_inventory WHERE quantity <= 0")
    
    async def get_inventory(self, user_id: int) -> List[dict]:
        if self.pool:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT i.name, inv.quantity, i.description 
                    FROM economy_inventory inv
                    JOIN economy_items i ON inv.item_id = i.id
                    WHERE inv.user_id = $1
                """, user_id)
                return [dict(r) for r in rows]
        return []
    
    async def log_tx(self, user_id: int, tx_type: str, amount: int, desc: str):
        if self.pool:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO economy_transactions (user_id, type, amount, description, timestamp)
                    VALUES ($1, $2, $3, $4)
                """, user_id, tx_type, amount, desc, int(time.time()))
    
    async def get_history(self, user_id: int, limit: int = 5) -> List[dict]:
        if self.pool:
            async with self.pool.acquire() as conn:
                limit = max(1, min(12, limit))
                rows = await conn.fetch("""
                    SELECT type, amount, timestamp, description
                    FROM economy_transactions
                    WHERE user_id = $1
                    ORDER BY id DESC LIMIT $2
                """, user_id, limit)
                return [dict(r) for r in rows]
        return []

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
                """, guild_id, json.dumps(config.to_dict()))
                
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