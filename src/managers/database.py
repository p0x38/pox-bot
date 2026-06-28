import asyncio

from src.managers.i18n import I18nManager

from ..database.economy import EconomyDatabase
from ..database.giveaway import GiveawayDatabase
from ..database.guild_v2 import GuildSettingsDatabase
from ..database.settings import SettingsDatabase
from ..database.stats import StatisticsDatabase
from ..database.user import UserDatabase


class DatabaseManager:
    def __init__(self, dsn: str, translation_manager: I18nManager):
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

        self.settings = SettingsDatabase(self.dsn, manager=self.translation_manager)
        self.stats = StatisticsDatabase(self.dsn)
        self.economy = EconomyDatabase(self.dsn)
        self.giveaway = GiveawayDatabase(self.dsn)
        self.guild = GuildSettingsDatabase(self.dsn)
        self.user = UserDatabase(self.dsn)

        await self.settings.connect()

        await self._batch_call("setup")

        self.loaded = True

    async def close(self):
        if not self.loaded:
            return

        await self._batch_call("close")

        self.loaded = False
