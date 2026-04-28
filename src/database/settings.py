from discord import Interaction
import orjson

from src.database import PostgreSQLDatabase
from logger import logger
from src.models import SettingsData
from src.translator import translator_instance as i18n
from src.utils import Cache


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
            return i18n._normalize_locale(cached_settings.locale)
        
        settings = await self.get_settings(user_id)
        if settings.locale:
            self.settings_cache.set(user_id, settings)
            return i18n._normalize_locale(settings.locale)
        
        return i18n._normalize_locale(interaction.locale)
    
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
            data_json = orjson.dumps(settings.to_dict()).decode('utf-8')
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO user_preferences (user_id, data)
                    VALUES ($1, $2::jsonb)
                    ON CONFLICT (user_id) DO UPDATE SET data = EXCLUDED.data
                """, user_id, data_json)