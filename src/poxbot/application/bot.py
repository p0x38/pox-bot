import asyncio
import gc
from datetime import datetime
from pathlib import Path

import nltk
from discord import (
    Color,
    DMChannel,
    Embed,
    Forbidden,
    GroupChannel,
    HTTPException,
    Interaction,
    InteractionType,
    Message,
    MissingApplicationID,
    StageChannel,
    TextChannel,
    Thread,
    VoiceChannel,
    app_commands,
)
from discord.abc import Messageable
from discord.ext import commands
from pytz import UTC

from ..features.statistics import BotConstants, BotStatistics, GitInfo
from ..features.text_transform.manager import TextTransformManager
from ..infrastructure.logger import get_logger
from ..infrastructure.logger.context import get_request_id, start_request
from ..infrastructure.logger.tracing import start_span
from ..services import (
    AntiSpamManager,
    DatabaseManager,
    ExtensionManager,
    ResourceManager,
    RuntimeState,
)
from ..services.counter import CounterManager
from ..shared.utils.cache import Cache
from ..shared.utils.metrics import Metrics
from ..shared.utils.perf_monitor import PerformanceMonitor
from .context import ApplicationContext


class PoxBot(commands.AutoShardedBot):
    """Main application bot class extending AutoShardedBot.

    This class serves as the central orchestrator for the Discord bot, managing
    database connections, localization/internationalization, application metrics,
    anti-spam filters, extensions and event dispatching.

    Attributes:
        config (BotSettings): The central configuration model containing settings
            for the database, tracing, prefixes, and other runtime parameters.
        logger (Logger | LoggerAdapter): The structured logging instance used to
            track bot actions, error traces, and operational metrics.
        i18n_manager (I18nManager): The core translation service used to handle
            multi-language asset loading and raw string manipulation.
        discord_translator (DiscordI18nTranslator): The dedicated translator
            hooked into the Discord API for application command localization.
        internal_translator (I18nTranslator): The translator instance used for
            formatting error messages, system notifications, and dynamic embeds.
        base_path (str | None): The root directory path of the bot application
            used to locate static resources and configurations.
        should_restart (bool): A state flag indicating whether the bot process
            should gracefully restart upon disconnection. Defaults to False.
        metrics (Metrics | None): The OpenTelemetry OTLP tracing and metrics
            pipeline pipeline. Initialized only if tracing is enabled in config.
        statistics (BotStatistics): Tracker for prefix commands, interactions,
            and session data.
        database (DatabaseManager): Management layer handling asynchronous
            connections and queries to the PostgreSQL database backend.
        resources (ResourceManager): Service responsible for caching and loading
            local static assets.
        runtime (RuntimeState): Thread-safe state tracker for volatile runtime
            flags and operational conditions.
        spam (AntiSpamManager): Security controller evaluating incoming messages
            against rate limits and repetitive content thresholds.
        constants (BotConstants): Immutable global settings, configurations,
            and exclusion lists used across the bot.
        git_info (GitInfo): Repository meta-information provider hosting the current
            commit hash, branch name, and deployment version.
        extension_manager (ExtensionManager): Dynamic cog loader responsible for
            discovering, loading, and reloading bot feature modules.
        shared_cache (Cache): Fast in-memory TTL cache with an automatic 120-second
            expiration policy for high-frequency database queries.
        perf_monitor (PerformanceMonitor): Event loop latency and task execution
            profiler aimed at identifying performance bottlenecks.
        text_converter (TextConversionManager): Utility pipeline specialized in
            sanitizing, normalizing, and filtering text payloads.
        counter_manager (CounterManager): Persistent JSON-backed counter tracking
            historical metrics and command usage numbers.
    """

    def __init__(
        self,
        context: ApplicationContext,
        *args,
        **kwargs,
    ) -> None:
        """Initialize the PoxBot instance and its dependent subsystems.

        Args:
            context (ApplicationContext): The application context for applications.
            *args: Variable length argument list forwarded to the parent
                commands.AutoShardedBot class.
            **kwargs: Arbitrary keyword arguments forwarded to the parent class.
                Expected to optionally contain 'root_path'.
        """
        super().__init__(*args, **kwargs)
        self.should_restart = False
        self.context = context

        self.settings = context.settings

        self.logger = get_logger(__name__, prefix='PoxBot')

        self.i18n_manager = context.i18n
        self.discord_translator = self.i18n_manager.discord
        self.internal_translator = self.i18n_manager.internal

        self.base_path = kwargs.get('root_path')

        if self.settings.trace_config.enabled:
            self.metrics = Metrics(self.settings.trace_config)
        else:
            self.metrics = None

        self.statistics = BotStatistics()
        self.database = DatabaseManager(
            bot=self,
            dsn=self.settings.database_config.build_url(),
            translation_manager=self.i18n_manager,
        )

        self.resources = ResourceManager()
        self.runtime = RuntimeState()
        self.spam = AntiSpamManager(self.database)
        self.constants = BotConstants()
        self.git_info = GitInfo()

        project_root = Path(__file__).resolve().parent.parent.parent

        actual_cogs_dir = 'poxbot/platforms/discord/extensions'
        actual_package = 'poxbot.platforms.discord.extensions'

        cogs_absolute_path = project_root / actual_cogs_dir
        self.extension_manager = ExtensionManager(
            cogs_path=str(cogs_absolute_path),
            package=actual_package,
            excluded_extensions=self.constants.exclude_extensions,
        )

        self.shared_cache = Cache(ttl=120)
        self.perf_monitor = PerformanceMonitor(self)
        self.text_converter = TextTransformManager(self.metrics)
        self.counter_manager = CounterManager(self)
        self.tasks: set[asyncio.Task] = set()

        self.tree.on_error = self._on_tree_error

    async def try_return_error(self, interaction: Interaction, **kwargs):
        """Send a message with detection of response if already respond."""
        if interaction.response.is_done():
            return await interaction.followup.send(**kwargs)
        return await interaction.response.send_message(**kwargs)

    async def load_extensions(self):
        """Loads all extensions using ExtensionManager."""
        result = await self.extension_manager.load_extensions(self)

        self.logger.info(
            'Loaded %d extensions (%d failed)',
            result.affected,
            result.failed,
            extra={
                'loaded_extensions': result.affected,
                'failed_extensions': result.failed,
                'duration_ms': result.operation_time_ms,
            },
        )

    async def sync_commands(self):
        """Custom method to sync application commands to Discord."""
        try:
            synced = await self.tree.sync()
            self.logger.info('Synchronized %d commands.', len(synced))
        except (
            app_commands.CommandSyncFailure,
            Forbidden,
            MissingApplicationID,
            app_commands.TranslationError,
            HTTPException,
        ) as e:
            if isinstance(e, app_commands.TranslationError):
                self.logger.exception(
                    'Failed to translate some strings for %s in %s (%s)',
                    e.string,
                    e.locale,
                    e.context.location.name,
                    extra={
                        'target': e.string,
                        'locale': e.locale,
                        'location': e.context.location.name,
                    },
                )
            else:
                self.logger.exception(
                    'An unexpected error was occurred while syncing commands',
                )

    async def setup_hook(self) -> None:
        def _download_nltk_data():
            try:
                nltk.data.find('tokenizers/punkt')
                nltk.data.find('corpora/stopwords')
            except LookupError:
                nltk.download('punkt', quiet=True)
                nltk.download('stopwords', quiet=True)

        await self.loop.run_in_executor(None, _download_nltk_data)

        if hasattr(self, 'counter_manager'):
            await self.counter_manager.load_async()

        try:
            await self.tree.set_translator(self.discord_translator)
        except TypeError:
            self.logger.exception('Failed to set command translator')

        await self.git_info.load()
        await self.resources.initialize()
        await self.database.connect()
        await self.load_extensions()
        await self.sync_commands()

        if self.metrics:
            self.metrics.start_server()
        self.logger.info('OpenTelemetry OTLP metrics pipeline has been initialized.')

    async def on_ready(self):
        with start_span('bot.ready'):
            self.logger.info(
                'Discord bot is ready to process!\nGuilds: (%s)',
                ', '.join([g.name for g in self.guilds]),
                extra={
                    'guilds': len(self.guilds),
                    'users': sum(g.member_count or 0 for g in self.guilds),
                },
            )

        gc.collect()
        self.logger.debug('Successfully ran garbage collection')

    async def on_message(self, message: Message):
        if message.author == self.user or message.mention_everyone:
            return

        request_id = start_request()

        with start_span('discord.message'):
            self.logger.info(
                '',
                extra={
                    'no_console': True,
                    'request_id': request_id,
                    'author_id': message.author.id,
                    'guild_id': message.guild.id if message.guild else None,
                    'channel_id': message.channel.id,
                },
            )

            if message.content.startswith(self.settings.bot_prefix):
                self.counter_manager.increment('total_prefix_commands_ran')
                await self.process_commands(message)

    async def on_command_completion(self, ctx: commands.Context):
        self.logger.info(
            '',
            extra={
                'command': str(ctx.command),
                'request_id': get_request_id(),
            },
        )

    async def on_command_error(self, ctx: commands.Context, e: commands.CommandError):
        try:
            self.logger.error(
                'Exception thrown while trying to process command: %s',
                e,
            )

            embed = Embed(
                title='Error thrown while trying to process the command!',
                timestamp=datetime.now(UTC),
                color=Color.red(),
            )

            await ctx.reply(embed=embed)
        except (HTTPException, Forbidden, TypeError, ValueError):
            self.logger.exception('Could not send error embed: %s')

    def format_channel_info(self, channel: Messageable | None):
        formatted_channel_identity = ''

        if not channel:
            return 'Null channel type'

        guild = getattr(channel, 'guild', None)
        prefix = f'{guild.name} - ' if guild else ''

        if isinstance(channel, (TextChannel, VoiceChannel, StageChannel)):
            formatted_channel_identity = (
                f'{prefix}{getattr(channel, "name", "Unknown")} '
                f'({getattr(channel, "id", "Unknown")})'
            )
        elif isinstance(channel, DMChannel):
            recipient = getattr(channel, 'recipient', None)
            formatted_channel_identity = (
                f"{recipient.name}'s DM" if recipient else 'DM Channel'
            )
        elif isinstance(channel, GroupChannel):
            if getattr(channel, 'name', None):
                return channel.name
            owner = getattr(channel, 'owner', None)
            formatted_channel_identity = (
                f"{owner.name}'s Group Chat" if owner else 'Group Chat channel'
            )
        elif isinstance(channel, Thread):
            if channel.parent:
                formatted_channel_identity = (
                    f"{channel.parent.name}'s thread {channel.name} "
                    f'by {channel.owner.display_name if channel.owner else "Nobody"}'
                )
        else:
            formatted_channel_identity = f'Unknown channel ({type(channel)})'

        return formatted_channel_identity

    async def on_interaction(self, interaction: Interaction):
        if (
            interaction.type == InteractionType.application_command
            and isinstance(interaction.command, app_commands.Command)
            and isinstance(
                interaction.channel,
                Messageable,
            )
        ):
            options = vars(interaction.namespace)

            self.logger.info(
                'User "%s" executed "/%s" in "%s"',
                f'{interaction.user.display_name} ({interaction.user.id})',
                interaction.command.qualified_name,
                self.format_channel_info(interaction.channel),
                extra={
                    'user': f'{interaction.user.display_name} ({interaction.user.id})',
                    'command': interaction.command.qualified_name,
                    'channel': self.format_channel_info(interaction.channel),
                    'command_args': options,
                    'guild_id': getattr(interaction.guild, 'id', None),
                },
            )
            self.statistics.interaction_statistics.count(interaction.command_failed)

    async def close(self) -> None:
        if hasattr(self, 'counter_manager'):
            await self.counter_manager.save_async()

        await self.database.close()
        await self.resources.close()

        return await super().close()

    async def reload_all_cogs(self):
        return await self.extension_manager.reload(self, '*')

    def get_uptime_seconds(self, start_timestamp: float) -> float:
        return (
            datetime.now(UTC) - datetime.fromtimestamp(start_timestamp, tz=UTC)
        ).total_seconds()

    async def get_locale(self, interaction: Interaction):
        return (
            await self.database.settings.get_locale(interaction)
            if (hasattr(self, 'database') and self.database and self.database.settings)
            else interaction.locale
        )

    async def _on_tree_error(
        self,
        interaction: Interaction,
        error: app_commands.AppCommandError,
    ):
        loc = await self.get_locale(interaction)
        error_name = error.__class__.__name__

        cmd_name = (
            interaction.command.qualified_name if interaction.command else 'unknown'
        )

        # key_templates = ["error.embeds_exceptions.{}", "error.exceptions.{}"]
        # TODO: use this for more fallbacks
        kwargs = {'e': str(error), 'mention': interaction.user.mention}

        if isinstance(error, app_commands.CommandOnCooldown):
            kwargs['remaining'] = str(round(error.retry_after, 2))
        if isinstance(
            error,
            (
                app_commands.MissingPermissions,
                app_commands.BotMissingPermissions,
            ),
        ):
            kwargs['permission'] = ', '.join(error.missing_permissions)

        cmd_name = (
            interaction.command.qualified_name
            if interaction.command
            else 'unknown command'
        )
        if isinstance(
            error,
            (app_commands.CommandInvokeError, app_commands.TransformerError),
        ):
            self.logger.error(
                'An uncaught error was thrown while processing a application command!',
                exc_info=error,
                extra={
                    'command': cmd_name,
                    'error_type': error.__class__.__name__,
                    'is_critical': isinstance(
                        error,
                        (
                            app_commands.CommandInvokeError,
                            app_commands.TransformerError,
                        ),
                    ),
                    'original_error_type': type(error.original).__name__
                    if isinstance(error, app_commands.CommandInvokeError)
                    else None,
                },
            )
        else:
            self.logger.warning('⚠️ User Error in /%s: %s', cmd_name, error)

        translator = getattr(self, 'internal_translator', None)

        target_error_name = (
            error.original.__class__.__name__
            if isinstance(error, app_commands.CommandInvokeError)
            else error_name
        )

        embed = None
        content = None

        if translator:
            embed_title_key = f'error.embed_exceptions.{target_error_name}.title'
            embed_desc_key = f'error.embed_exceptions.{target_error_name}.description'

            title_res = translator.T(embed_title_key, str(loc), kwargs)
            desc_res = translator.T(embed_desc_key, str(loc), kwargs)

            if title_res != embed_title_key or desc_res != embed_desc_key:
                embed = Embed(
                    title=(
                        title_res
                        if title_res != embed_title_key
                        else f'Error: {target_error_name}'
                    ),
                    description=(desc_res if desc_res != embed_desc_key else ''),
                    color=Color.red(),
                    timestamp=datetime.now(UTC),
                )
            else:
                text_key = f'error.exceptions.{target_error_name}'
                text_res = translator.T(text_key, str(loc), kwargs)

                if text_res == text_key:
                    text_res = translator.T(
                        'error.exceptions.AppCommandError',
                        str(loc),
                        kwargs,
                    )

                content = text_res
        else:
            description = f'An error occurred while executing the command: `{error}`'
            embed = Embed(
                title=f'Error: {target_error_name}',
                description=description,
                color=Color.red(),
                timestamp=datetime.now(UTC),
            )

        if interaction.type == InteractionType.application_command:
            if embed:
                await self.try_return_error(interaction, embed=embed)
            else:
                await self.try_return_error(interaction, content=content)
        elif interaction.type == InteractionType.autocomplete:
            self.logger.error(
                'Error thrown while trying to resolve autocompletion: %s',
                content or (embed.description if embed else 'Unknown error'),
            )
        else:
            self.logger.error(
                'An unexpected error was occurred: %s',
                content or (embed.description if embed else 'Unknown error'),
            )
