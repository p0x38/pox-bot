from discord import Interaction

from src.bases import BaseDatabase
from src.managers.i18n import I18nManager
from src.models.user_settings import SettingsData
from src.models.user_settings_orm import UserPreference
from src.utils import Cache


class SettingsDatabase(BaseDatabase):
    def __init__(self, dsn: str, manager: I18nManager):
        super().__init__(dsn)
        self.settings_cache = Cache(ttl=600)
        self.manager = manager

    async def get_locale(self, interaction: Interaction) -> str:
        user_id = interaction.user.id
        internal = self.manager.internal

        cached = self.settings_cache.get(user_id)
        if cached and cached.locale:
            return internal._normalize_locale(cached.locale)

        settings = await self.get_settings(user_id)
        if settings.locale:
            return internal._normalize_locale(settings.locale)

        return internal._normalize_locale(interaction.locale)

    async def get_settings(self, user_id: int, use_cache: bool = True) -> SettingsData:
        if use_cache:
            cached = self.settings_cache.get(user_id)
            if cached:
                return cached

        async with self.async_session() as session:
            pref = await session.get(UserPreference, user_id)
            settings = pref.data if pref else SettingsData()

            self.settings_cache.set(user_id, settings)
            return settings

    async def set_settings(self, user_id: int, settings: SettingsData):
        if isinstance(settings.locale, list):
            settings.locale = settings.locale[0] if settings.locale else 'en'

        self.settings_cache.set(user_id, settings)

        async with self.async_session() as session, session.begin():
            await session.merge(UserPreference(user_id=user_id, data=settings))
