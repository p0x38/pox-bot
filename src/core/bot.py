from datetime import datetime
from logging import Logger

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

import stuff
from src.managers.i18n import I18nManager
from src.utils.cache import Cache
from src.utils.perf_monitor import PerformanceMonitor

from ..config.schema import BotSettings
from ..i18n_processor.translator import DiscordI18nTranslator, I18nTranslator
from ..managers import AntiSpamManager, DatabaseManager, ExtensionManager, ResourceManager, RuntimeState
from ..statistics import BotConstants, BotStatistics, GitInfo


class PoxBot(commands.AutoShardedBot):
    def __init__(
        self,
        config: BotSettings,
        logger: Logger,
        translation_manager: I18nManager,
        discord_translator: DiscordI18nTranslator,
        internal_translator: I18nTranslator,
        *args, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)

        self.config = config
        self.logger = logger
        self.i18n_manager = translation_manager
        self.discord_translator = discord_translator
        self.internal_translator = internal_translator

        self.statistics = BotStatistics()
        self.database = DatabaseManager(
            dsn=config.database_config.build_url() if config else stuff.get_postgresql_dsn(),
            translation_manager=translation_manager
        )

        self.resources = ResourceManager()
        self.runtime = RuntimeState()
        self.spam = AntiSpamManager()
        self.constants = BotConstants()
        self.git_info = GitInfo()
        self.extension_manager = ExtensionManager(excluded_extensions=self.constants.exclude_extensions)
        self.shared_cache = Cache(ttl=120)
        self.perf_monitor = PerformanceMonitor(self)

    async def load_extensions(self):
        result = await self.extension_manager.load_extensions(
            self
        )

        self.logger.info("Loaded %d extensions (%d failed)", result.affected, result.failed)

    async def sync_commands(self):
        try:
            synced = await self.tree.sync()
            self.logger.info(f"Synchronized {len(synced)} commands.")
        except (app_commands.CommandSyncFailure, Forbidden, MissingApplicationID,
                app_commands.TranslationError, HTTPException) as e:
            if isinstance(e, app_commands.TranslationError):
                self.logger.exception(
                    f"Error thrown while translating key {e.string!s} in {e.locale} ({e.context.location.name})"
                )
            else:
                self.logger.exception("Error thrown while trying to sync commands")

    async def setup_hook(self) -> None:
        def _download_nltk_data():
            import nltk
            nltk.download('punkt')
            nltk.download('stopwords')

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

    async def on_ready(self):
        if self.user:
            self.logger.info("\n".join((
                "The client has been logged in into a bot!",
                f"User ID: {self.user.id}",
                f"Username: {self.user.name}",
                f"Connected guilds: {len(self.guilds)}",
                f"Guilds: {', '.join([guild.name for guild in self.guilds])}",
                f"Users: {len(self.users)}"
            )))
        else:
            self.logger.info("It seems client is not connected")

    async def on_message(self, message: Message):
        if message.author == self.user or message.mention_everyone:
            return

        if message.content.startswith("pox!"):
            self.statistics.count_prefix_command()
            await self.process_commands(message)

    async def on_command_error(self, ctx: commands.Context, e: commands.CommandError):
        try:
            self.logger.error(f"Exception thrown while trying to process command: {e}")

            embed = Embed(
                title="Error thrown while trying to process the command!",
                timestamp=datetime.now(UTC),
                color=Color.red()
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
                    f"by {channel.owner.display_name if channel.owner else "Nobody"}"
                )
        else:
            formatted_channel_identity = f"Unknown channel ({type(channel)})"

        return formatted_channel_identity

    async def on_interaction(self, interaction: Interaction):
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
