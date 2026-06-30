import asyncio
from time import perf_counter
from typing import TYPE_CHECKING

from src.managers.i18n import I18nManager

from ..database.economy import EconomyDatabase
from ..database.giveaway import GiveawayDatabase
from ..database.guild_v2 import GuildSettingsDatabase
from ..database.settings import SettingsDatabase
from ..database.stats import StatisticsDatabase
from ..database.user import UserDatabase

if TYPE_CHECKING:
    from src.core.bot import PoxBot  # noqa: F811


class DatabaseManager:
    def __init__(self, bot: "PoxBot", dsn: str, translation_manager: I18nManager):
        self.bot = bot
        self.dsn = dsn
        self.translation_manager = translation_manager

        self.settings: SettingsDatabase | None = None
        self.stats: StatisticsDatabase | None = None
        self.economy: EconomyDatabase | None = None
        self.giveaway: GiveawayDatabase | None = None
        self.guild: GuildSettingsDatabase | None = None
        self.user: UserDatabase | None = None

        self.loaded: bool = False

    @property
    def databases(self):
        return [db for db in (
            self.settings, self.stats, self.economy,
            self.giveaway, self.guild, self.user
        ) if db is not None]
    
    async def _set_status_gauge(self, value: float):
        if self.bot and getattr(self.bot, "metrics", None):
            self.bot.metrics.set_gauge(
                name="bot_database_status",
                description="Database connectivity status (1 for connected, 0 for disconnected)",
                value=value,
            )

    async def _batch_call(self, method_name: str):
        await asyncio.gather(
            *(
                getattr(database, method_name)()
                for database in self.databases
            )
        )

    async def connect(self):
        if self.loaded:
            return
        
        start_time = perf_counter()

        self.settings = SettingsDatabase(self.dsn, manager=self.translation_manager)
        self.stats = StatisticsDatabase(self.dsn)
        self.economy = EconomyDatabase(self.dsn)
        self.giveaway = GiveawayDatabase(self.dsn)
        self.guild = GuildSettingsDatabase(self.dsn)
        self.user = UserDatabase(self.dsn)

        await self.settings.connect()

        await self._batch_call("setup")

        self.loaded = True
        
        init_duration = perf_counter() - start_time
        if self.bot and getattr(self.bot, "metrics", None):
            self.bot.metrics.record_histogram(
                name="bot_database_init_duration_seconds",
                description="The total initialization and setup duration of all database components in seconds",
                value=init_duration
            )
        
        await self._set_status_gauge(1.0)

    async def close(self):
        if not self.loaded:
            return

        await self._batch_call("close")

        self.loaded = False
        
        await self._set_status_gauge(0.0)
