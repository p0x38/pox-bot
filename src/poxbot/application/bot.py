import asyncio
import gc
from datetime import datetime

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
from sqlalchemy.exc import SQLAlchemyError

from ..core.cache import Cache
from ..features.earthquake.p2pquake import P2PQuakeManager
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
from ..shared.utils.metrics import get_or_create_metrics
from ..shared.utils.perf_monitor import PerformanceMonitor
from .command_tree import ModerationCommandTree
from .context import ApplicationContext
from .shutdown import shutdown
from .startup import startup


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
        kwargs.setdefault('tree_cls', ModerationCommandTree)
        super().__init__(*args, **kwargs)
        self.should_restart = False
        self.context = context

        self.settings = context.settings

        self.logger = get_logger(__name__, prefix='PoxBot')

        self.i18n_manager = context.i18n
        self.discord_translator = self.i18n_manager.discord
        self.internal_translator = self.i18n_manager.internal

        self.base_path = kwargs.get('root_path')

        self.metrics = (
            get_or_create_metrics(self.settings.trace_config)
            if self.settings.trace_config.enabled
            else None
        )

        self.statistics = BotStatistics()
        self.database = DatabaseManager(
            bot=self,
            dsn=self.settings.database_config.build_url(),
            translation_manager=self.i18n_manager,
        )

        self.add_check(self._check_prefix_botban)

        self.resources = ResourceManager()
        self.runtime = RuntimeState()
        self.spam = AntiSpamManager(self.database)
        self.constants = BotConstants()
        self.git_info = GitInfo()

        actual_package = 'poxbot.platforms.discord.extensions'
        cogs_absolute_path = context.resource_manager.resolve_path(
            'extensions:poxbot/platforms/discord/extensions',
        )
        self.extension_manager = ExtensionManager(
            cogs_path=str(cogs_absolute_path),
            package=actual_package,
            excluded_extensions=self.constants.exclude_extensions,
            resource_manager=context.resource_manager,
        )

        self.shared_cache = Cache(
            ttl=120,
            max_memory_entries=1024,
        )
        self.perf_monitor = PerformanceMonitor(self)
        self.text_converter = TextTransformManager(self.metrics)
        self.counter_manager = CounterManager(self)
        self.tasks: set[asyncio.Task] = set()

        self.quake_manager = P2PQuakeManager(cache_size=100)

        self.tree.on_error = self._on_tree_error

    async def is_bot_banned(self, user_id: int) -> bool:
        database = self.database.guild
        if database is None:
            return False

        now = datetime.now(UTC).timestamp()
        entries = await database.get_moderation_entries(
            item_type='user',
            item_scope=-2,
        )

        return any(
            entry.value == str(user_id)
            and (entry.expires_at is None or entry.expires_at > now)
            for entry in entries
        )

    async def _check_prefix_botban(
        self,
        ctx: commands.Context,
    ) -> bool:
        if not await self.is_bot_banned(ctx.author.id):
            return True

        key = 'error.custom.user_restricted_from_using_commands'
        locale = ctx.guild.preferred_locale.value if ctx.guild else 'en'
        message = self.internal_translator.T(key, locale)

        if message == key:
            message = 'You are restricted from using this bot.'

        await ctx.reply(message, mention_author=False)
        return False

    async def try_return_error(self, interaction: Interaction, **kwargs):
        """Send a message with detection of response if already respond."""
        if interaction.response.is_done():
            return await interaction.followup.send(**kwargs)
        return await interaction.response.send_message(**kwargs)

    async def load_extensions(self) -> None:
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

    async def sync_commands(self) -> None:
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
                    'Failed to synchronize application commands; '
                    'commands may be stale.',
                    extra={'error_type': type(e).__name__},
                )

    async def setup_hook(self) -> None:
        await startup(self)

    async def on_ready(self) -> None:
        with start_span('bot.ready'):
            self.logger.info(
                'Discord bot is ready to process!',
            )

            guilds = sorted(
                self.guilds,
                key=lambda g: g.id,
            )
            self.logger.info(
                '### Guilds ###\n%s',
                '\n'.join([f'{g.id}: "{g.name}"' for g in guilds]),
                extra={
                    'guilds': len(guilds),
                    'users': sum(g.member_count or 0 for g in guilds),
                },
            )

        gc.collect()
        self.logger.debug('Successfully ran garbage collection')

    async def on_message(self, message: Message) -> None:
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

            if message.content.startswith(self.settings.bot_config.bot_prefix):
                self.counter_manager.increment('total_prefix_commands_ran')
                await self.process_commands(message)

    async def on_command_completion(self, ctx: commands.Context) -> None:
        self.logger.info(
            '',
            extra={
                'command': str(ctx.command),
                'request_id': get_request_id(),
            },
        )

    async def on_command_error(self, ctx: commands.Context, e: commands.CommandError):
        self.logger.error(
            'Exception thrown while trying to process command: %s',
            e,
            exc_info=(type(e), e, e.__traceback__),
            extra={'command': str(ctx.command)},
        )

        title_key = 'error.embeds.generic.title'
        title = (
            self.internal_translator.T(
                title_key,
                ctx.guild.preferred_locale.value if ctx.guild else 'en',
            )
            if self.internal_translator
            else 'Error'
        )
        if title == title_key:
            title = 'Error'

        embed = Embed(
            title=title,
            timestamp=datetime.now(UTC),
            color=Color.red(),
        )
        try:
            await ctx.reply(embed=embed)
        except HTTPException as send_error:
            self.logger.exception(
                'Could not send error embed for command %s: %s',
                ctx.command,
                send_error,
                extra={'command': str(ctx.command)},
            )

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
        request_id = start_request()

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
                    'request_id': request_id,
                },
            )
            self.statistics.interaction_statistics.count(interaction.command_failed)

    async def close(self) -> None:
        try:
            await shutdown(self)
        finally:
            await super().close()

    async def reload_all_cogs(self):
        return await self.extension_manager.reload(self, '*')

    def get_uptime_seconds(self, start_timestamp: float) -> float:
        return (
            datetime.now(UTC) - datetime.fromtimestamp(start_timestamp, tz=UTC)
        ).total_seconds()

    async def get_locale(
        self,
        interaction: Interaction,
        *,
        prefer_guild: bool = False,
    ):
        if prefer_guild and interaction.guild_locale:
            return interaction.locale

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
        cmd_name = (
            interaction.command.qualified_name
            if interaction.command
            else 'unknown command'
        )

        try:
            loc = await self.get_locale(interaction)
        except (SQLAlchemyError, TimeoutError):
            self.logger.exception(
                'Failed to resolve locale while handling /%s; using Discord locale',
                cmd_name,
                extra={'command': cmd_name, 'error_type': type(error).__name__},
            )
            loc = interaction.locale

        error_name = error.__class__.__name__
        kwargs = {'e': 'internal error', 'mention': interaction.user.mention}

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

        if isinstance(
            error,
            (app_commands.CommandInvokeError, app_commands.TransformerError),
        ):
            cause = (
                error.original
                if isinstance(error, app_commands.CommandInvokeError)
                else error.__cause__ or error
            )
            self.logger.error(
                'An uncaught error was thrown while processing an application command.',
                exc_info=(type(cause), cause, cause.__traceback__),
                extra={
                    'command': cmd_name,
                    'error_type': error.__class__.__name__,
                    'is_critical': True,
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

        generic_title = 'Error'
        generic_description = (
            'Something went wrong while processing the command. Please try again.'
        )

        if translator:
            generic_title_key = 'error.embeds.generic.title'
            generic_description_key = 'error.embeds.generic.description'
            translated_generic_title = translator.T(generic_title_key, str(loc))
            translated_generic_description = translator.T(
                generic_description_key,
                str(loc),
            )
            if translated_generic_title != generic_title_key:
                generic_title = translated_generic_title
            if translated_generic_description != generic_description_key:
                generic_description = translated_generic_description

            embed_title_key = f'error.embed_exceptions.{target_error_name}.title'
            embed_desc_key = f'error.embed_exceptions.{target_error_name}.description'

            title_res = translator.T(embed_title_key, str(loc), kwargs)
            desc_res = translator.T(embed_desc_key, str(loc), kwargs)

            if title_res != embed_title_key or desc_res != embed_desc_key:
                embed = Embed(
                    title=(
                        title_res if title_res != embed_title_key else generic_title
                    ),
                    description=(
                        desc_res if desc_res != embed_desc_key else generic_description
                    ),
                    color=Color.red(),
                    timestamp=datetime.now(UTC),
                )
            else:
                text_key = f'error.exceptions.{target_error_name}'
                text_res = translator.T(text_key, str(loc), kwargs)

                if text_res == text_key:
                    fallback_text_key = 'error.exceptions.AppCommandError'
                    text_res = translator.T(
                        fallback_text_key,
                        str(loc),
                        kwargs,
                    )

                if text_res not in (text_key, 'error.exceptions.AppCommandError'):
                    content = text_res

        if embed is None and content is None:
            embed = Embed(
                title=generic_title,
                description=generic_description,
                color=Color.red(),
                timestamp=datetime.now(UTC),
            )

        if interaction.type == InteractionType.application_command:
            try:
                if embed:
                    await self.try_return_error(interaction, embed=embed)
                else:
                    await self.try_return_error(interaction, content=content)
            except HTTPException:
                self.logger.exception(
                    'Failed to send error response for /%s',
                    cmd_name,
                    extra={'command': cmd_name, 'error_type': error_name},
                )
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
