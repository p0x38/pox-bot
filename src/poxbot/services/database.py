import asyncio
from time import perf_counter
from typing import TYPE_CHECKING

from ..features.markov.storage import MarkovDatabase
from ..infrastructure.logger.tracing import traced
from ..persistence.database.economy import EconomyDatabase
from ..persistence.database.giveaway import GiveawayDatabase
from ..persistence.database.guild_v2 import GuildSettingsDatabase
from ..persistence.database.metrics import MetricsDatabase
from ..persistence.database.settings import SettingsDatabase
from ..persistence.database.stats import StatisticsDatabase
from ..persistence.database.user import UserDatabase
from ..services.i18n import I18nManager

if TYPE_CHECKING:
    from ..application.bot import PoxBot


class DatabaseManager:
    def __init__(
        self,
        bot: 'PoxBot',
        dsn: str,
        translation_manager: I18nManager,
    ):
        self.bot = bot
        self.dsn = dsn
        self.translation_manager = translation_manager

        self.settings: SettingsDatabase | None = None
        self.stats: StatisticsDatabase | None = None
        self.economy: EconomyDatabase | None = None
        self.giveaway: GiveawayDatabase | None = None
        self.guild: GuildSettingsDatabase | None = None
        self.user: UserDatabase | None = None
        self.metrics: MetricsDatabase | None = None
        self.markov: MarkovDatabase | None = None

        self.loaded: bool = False

    @property
    def databases(self):
        return [
            db
            for db in (
                self.settings,
                self.stats,
                self.economy,
                self.giveaway,
                self.guild,
                self.user,
                self.metrics,
                self.markov,
            )
            if db is not None
        ]

    async def _set_status_gauge(self, value: float):
        if self.bot.metrics:
            self.bot.metrics.set_gauge(
                name='bot_database_status',
                description=(
                    'Database connectivity status '
                    '(1 for connected, 0 for disconnected)'
                ),
                value=value,
            )

    async def _batch_call(self, method_name: str):
        await asyncio.gather(
            *(
                getattr(database, method_name)()
                for database in self.databases
            ),
        )

    @traced('db.connect')
    async def connect(self):
        if self.loaded:
            return

        start_time = perf_counter()

        async def _do_connect():
            self.settings = SettingsDatabase(
                self.bot,
                self.dsn,
                manager=self.translation_manager,
            )
            self.stats = StatisticsDatabase(
                self.bot,
                self.dsn,
            )
            self.economy = EconomyDatabase(
                self.bot,
                self.dsn,
            )
            self.giveaway = GiveawayDatabase(
                self.bot,
                self.dsn,
            )
            self.guild = GuildSettingsDatabase(
                self.bot,
                self.dsn,
            )
            self.user = UserDatabase(
                self.bot,
                self.dsn,
            )
            self.metrics = MetricsDatabase(
                self.bot,
                self.dsn,
            )
            self.markov = MarkovDatabase(
                self.bot,
                self.dsn,
            )

            await self._batch_call('connect')
            await self._batch_call('setup')

        if self.bot.metrics:
            async with self.bot.metrics.span_async(
                'bot_database_connect',
                component='database',
                dsn=self.dsn,
            ):
                await _do_connect()
        else:
            await _do_connect()

        self.loaded = True

        init_duration = perf_counter() - start_time

        if self.bot.metrics:
            self.bot.metrics.record_histogram(
                name='bot_database_init_duration_seconds',
                description=(
                    'The total initialization and setup duration '
                    'of all database components in seconds'
                ),
                value=init_duration,
            )

        await self._set_status_gauge(1.0)

    async def close(self):
        if not self.loaded:
            return

        await self._batch_call('close')

        self.loaded = False

        await self._set_status_gauge(0.0)
