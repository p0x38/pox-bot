from typing import TYPE_CHECKING

from discord import Interaction

from ...shared.bases.base_orm_model import Base

from ...shared.bases import BaseDatabase
from ...shared.utils import Cache
from ..models.user_settings import SettingsData
from ..models.user_settings_orm import UserPreference

if TYPE_CHECKING:
    from ...application.bot import PoxBot
    from ...services.i18n import I18nManager


class SettingsDatabase(BaseDatabase):
    def __init__(self, bot: 'PoxBot', dsn: str, manager: 'I18nManager'):
        super().__init__(bot, dsn)
        self.settings_cache = Cache(ttl=600)
        self.manager = manager
    
    async def on_load(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.logger.debug("Initialized tables")
    

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

        async with self.async_session() as session, session.begin():
            pref = await session.get(UserPreference, user_id)
            settings = pref.data if pref else SettingsData()

        self.settings_cache.set(user_id, settings)
        return settings

    async def set_settings(self, user_id: int, settings: SettingsData):
        if isinstance(settings.locale, list):
            settings.locale = settings.locale[0] if settings.locale else 'en'

        async with self.async_session() as session, session.begin():
            pref = await session.get(UserPreference, user_id) or UserPreference(
                user_id=user_id,
            )
            pref.data = settings
            await session.merge(pref)

        self.settings_cache.set(user_id, settings)
