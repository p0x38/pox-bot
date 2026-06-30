import traceback
from datetime import datetime
from logging import Logger, LoggerAdapter
from time import perf_counter

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
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBasedTraceIdRatio
from pytz import UTC

import stuff
from src.managers.i18n import I18nManager
from src.managers.text_filter import TextConversionManager
from src.utils.cache import Cache
from src.utils.metrics import Metrics
from src.utils.perf_monitor import PerformanceMonitor

from ..config.schema import BotSettings
from ..i18n_processor.translator import DiscordI18nTranslator, I18nTranslator
from ..managers import AntiSpamManager, DatabaseManager, ExtensionManager, ResourceManager, RuntimeState
from ..statistics import BotConstants, BotStatistics, GitInfo


class PoxBot(commands.AutoShardedBot):
    def __init__(
        self,
        config: BotSettings,
        logger: Logger | LoggerAdapter,
        translation_manager: I18nManager,
        discord_translator: DiscordI18nTranslator,
        internal_translator: I18nTranslator,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.should_restart = False

        self.config = config
        self.logger = logger
        self.i18n_manager = translation_manager
        self.discord_translator = discord_translator
        self.internal_translator = internal_translator
        self.base_path = kwargs.get("root_path")

        if config.trace_config.enabled:
            resource = Resource(attributes={
                "service.name": "pox-discord-bot",
                "service.instance.id": "p0x38-discord.py-bot-2026",
            })
            sampler = ParentBasedTraceIdRatio(config.trace_config.sampling_ratio)

            trace_provider = TracerProvider(resource=resource, sampler=sampler)

            trace_provider.add_span_processor(
                BatchSpanProcessor(
                    OTLPSpanExporter(
                        endpoint=config.trace_config.opentelemetry_endpoint,
                        insecure=config.trace_config.insecure
                    ),
                    max_queue_size=config.trace_config.max_batch_size * 4,
                    max_export_batch_size=config.trace_config.max_batch_size,
                    schedule_delay_millis=config.trace_config.export_interval_ms,
                )
            )
            trace.set_tracer_provider(trace_provider)
            self.metrics = Metrics(config.trace_config)

        self.statistics = BotStatistics()
        self.database = DatabaseManager(
            bot=self,
            dsn=config.database_config.build_url() if config else stuff.get_postgresql_dsn(),
            translation_manager=translation_manager,
        )

        self.resources = ResourceManager()
        self.runtime = RuntimeState()
        self.spam = AntiSpamManager(self.database)
        self.constants = BotConstants()
        self.git_info = GitInfo()
        self.extension_manager = ExtensionManager(excluded_extensions=self.constants.exclude_extensions)
        self.shared_cache = Cache(ttl=120)
        self.perf_monitor = PerformanceMonitor(self)
        self.text_converter = TextConversionManager()

        self.tree.on_error = self._on_tree_error

    async def try_return_error(self, interaction: Interaction, **kwargs):
        if interaction.response.is_done():
            return await interaction.followup.send(**kwargs)
        return await interaction.response.send_message(**kwargs)

    async def load_extensions(self):
        result = await self.extension_manager.load_extensions(self)

        self.logger.info("Loaded %d extensions (%d failed)", result.affected, result.failed)

    async def sync_commands(self):
        try:
            synced = await self.tree.sync()
            self.logger.info(f"Synchronized {len(synced)} commands.")
        except (
            app_commands.CommandSyncFailure,
            Forbidden,
            MissingApplicationID,
            app_commands.TranslationError,
            HTTPException,
        ) as e:
            if isinstance(e, app_commands.TranslationError):
                self.logger.exception(
                    f"Error thrown while translating key {e.string!s} in {e.locale} ({e.context.location.name})"
                )
            else:
                self.logger.exception("Error thrown while trying to sync commands")

    async def setup_hook(self) -> None:
        def _download_nltk_data():
            import nltk

            nltk.download("punkt")
            nltk.download("stopwords")

        await self.loop.run_in_executor(None, _download_nltk_data)

        try:
            await self.tree.set_translator(self.discord_translator)
        except TypeError:
            self.logger.exception("Failed to set command translator")

        await self.git_info.load()
        await self.resources.initialize()
        await self.database.connect()
        await self.load_extensions()
        await self.sync_commands()

        self.metrics.start_server()
        self.logger.info("OpenTelemetry OTLP metrics pipeline initialized.")

    async def on_ready(self):
        if self.user:
            self.logger.info(
                "\n".join((
                    "The client has been logged in into a bot!",
                    f"User ID: {self.user.id}",
                    f"Username: {self.user.name}",
                    f"Connected guilds: {len(self.guilds)}",
                    f"Guilds: {', '.join([guild.name for guild in self.guilds])}",
                    f"Users: {len(self.users)}",
                ))
            )
        else:
            self.logger.info("It seems client is not connected")

    async def on_message(self, message: Message):
        if message.author == self.user or message.mention_everyone:
            return

        if message.content.startswith(self.config.bot_prefix):
            self.statistics.count_prefix_command()
            await self.process_commands(message)

    async def on_command_error(self, ctx: commands.Context, e: commands.CommandError):
        try:
            self.logger.error(f"Exception thrown while trying to process command: {e}")

            embed = Embed(
                title="Error thrown while trying to process the command!", timestamp=datetime.now(UTC), color=Color.red()
            )

            await ctx.reply(embed=embed)
        except (HTTPException, Forbidden, TypeError, ValueError) as e2:
            self.logger.error(f"Could not send error embed: {e2}")

    def format_channel_info(self, channel: Messageable | None):
        formatted_channel_identity = ""

        if not channel:
            return "Null channel type"

        guild = getattr(channel, "guild", None)
        if guild:
            formatted_channel_identity = f"{guild.name} - "

        if isinstance(channel, DMChannel):
            recipient = getattr(channel, "recipient", None)
            formatted_channel_identity = f"{recipient.name}'s DM" if recipient else "DM Channel"
        elif isinstance(channel, GroupChannel):
            if channel.name:
                return channel.name
            owner = getattr(channel, "owner", None)
            formatted_channel_identity = f"{owner.name}'s Group Chat" if owner else "Group Chat channel"
        elif isinstance(channel, (TextChannel, VoiceChannel, StageChannel)):
            formatted_channel_identity = f"{channel.name} ({channel.id})"
        elif isinstance(channel, Thread):
            if channel.parent:
                formatted_channel_identity = (
                    f"{channel.parent.name}'s thread {channel.name} "
                    f"by {channel.owner.display_name if channel.owner else 'Nobody'}"
                )
        else:
            formatted_channel_identity = f"Unknown channel ({type(channel)})"

        return formatted_channel_identity

    async def on_interaction(self, interaction: Interaction):
        interaction.extras["start_time"] = perf_counter()
        if interaction.type == InteractionType.application_command:
            if isinstance(interaction.command, app_commands.Command) and isinstance(interaction.channel, Messageable):
                options = vars(interaction.namespace)

                self.logger.info(
                    '"%s" used "/%s" at "%s" (args: %s)',
                    f"{interaction.user.display_name} ({interaction.user.id})",
                    interaction.command.qualified_name,
                    f"{self.format_channel_info(interaction.channel)}",
                    ", ".join(f"{k}={v!r}" for k, v in options.items()) or "None",
                )
            self.statistics.interaction_statistics.count(interaction.command_failed)

    async def close(self) -> None:
        await self.database.close()
        await self.resources.close()

        return await super().close()

    async def reload_all_cogs(self):
        return await self.extension_manager.reload(self, "*")

    def get_uptime_seconds(self, start_timestamp: float) -> float:
        return (datetime.now(UTC) - datetime.fromtimestamp(start_timestamp, tz=UTC)).total_seconds()

    async def get_locale(self, interaction: Interaction):
        loc = (
            await self.database.settings.get_locale(interaction)
            if (hasattr(self, "database") and self.database and self.database.settings)
            else interaction.locale
        )
        return loc

    async def _on_tree_error(self, interaction: Interaction, error: app_commands.AppCommandError):
        loc = await self.get_locale(interaction)
        error_name = error.__class__.__name__

        cmd_name = interaction.command.qualified_name if interaction.command else "unknown"

        # key_templates = ["error.embeds_exceptions.{}", "error.exceptions.{}"]  # TODO: use this for more fallbacks
        key = "error.exceptions.{}"
        kwargs = {"e": str(error)}

        if isinstance(error, app_commands.CommandOnCooldown):
            kwargs["remaining"] = str(round(error.retry_after, 2))

        cmd_name = interaction.command.qualified_name if interaction.command else "unknown command"
        if isinstance(error, (app_commands.CommandInvokeError, app_commands.TransformerError)):
            self.logger.error(f"🔴 Critical Error in /{cmd_name}: {error}")
            if isinstance(error, app_commands.CommandInvokeError):
                self.logger.error(
                    "".join(traceback.format_exception(type(error.original), error.original, error.original.__traceback__))
                )
        else:
            self.logger.warning(f"⚠️ User Error in /{cmd_name}: {error}")

        translator = getattr(self, "internal_translator", None)

        if translator:
            description = translator.T(key.format(error_name), str(loc), kwargs)
            if description == key:
                description = translator.T("error.exceptions.AppCommandError", str(loc), kwargs)
        else:
            description = f"An error occurred while executing the command: `{error}`"

        if isinstance(error, app_commands.CommandInvokeError) and translator:
            original_error_name = error.original.__class__.__name__
            original_key = key.format(original_error_name)
            original_description = translator.T(original_key, str(loc), kwargs)

            if original_description == original_key:
                original_description = translator.T("error.exceptions.Unknown", str(loc), e=original_error_name)

            description += f"\n\n**Original Error:** {original_description}"

        if interaction.type == InteractionType.application_command:
            embed = Embed(
                title=f"Error: {error_name}",
                description=description,
                color=Color.red(),
                timestamp=datetime.now(UTC),
            )

            await self.try_return_error(interaction, embed=embed)
        elif interaction.type == InteractionType.autocomplete:
            self.logger.error(f"Error thrown while trying to resolve autocompletion stuff\n{description}")
