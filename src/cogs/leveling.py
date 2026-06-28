import contextlib
import random
from datetime import datetime, timedelta

from discord import (
    Color,
    Embed,
    Forbidden,
    Interaction,
    Member,
    Message,
    TextChannel,
    User,
    app_commands,
)
from discord.abc import Messageable
from discord.ext import commands
from pytz import UTC

from src.bot import PoxBot


class LevelingCog(commands.Cog):
    def __init__(self, bot: PoxBot):
        self.bot = bot
        self.cooldowns: dict[int, datetime] = {}

    group = app_commands.Group(
        name="leveling", description=app_commands.locale_str("command.leveling.description"))

    async def get_working_locale(self, target: Member | User | Interaction) -> str:
        if isinstance(target, Interaction):
            return await self.bot.settings_db.get_locale(
                target) if self.bot.settings_db else target.locale.value

        if self.bot.settings_db:
            data = await self.bot.settings_db.get_settings(target.id)
            if data and data.locale:
                return data.locale

        return target.guild.preferred_locale.value if isinstance(
            target, Member) and target.guild else "en"

    def calculate_xp(self, message: Message, multiplier: float = 1.0) -> int:
        content = message.content
        if not content:
            return int(random.randint(5, 10) * multiplier)

        words = content.split()
        word_bonus = min(len(words) // 2, 24)
        char_bonus = min(len(content) // 10, 24)

        base_xp = random.randint(10, 20)
        total_xp = (base_xp + word_bonus + char_bonus) * multiplier

        return int(min(total_xp, 128))

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if message.author.bot or not message.guild or not self.bot.guild_db:
            return

        config = await self.bot.guild_db.get_config(message.guild.id)
        lev_cfg = config.leveling

        if not lev_cfg.enabled:
            return

        last_gain = self.cooldowns.get(message.author.id)
        if last_gain and datetime.now(UTC) - last_gain < timedelta(minutes=1):
            return

        xp_gain = self.calculate_xp(message, multiplier=lev_cfg.xp_rate)

        if self.bot.stats_db:
            result = await self.bot.stats_db.add_xp(message.author.id, xp_gain)
            self.cooldowns[message.author.id] = datetime.now(UTC)

            if result and result.get('leveled_up') and lev_cfg.notify:
                loc = await self.get_working_locale(message.author)

                embed = Embed(
                    description=self.bot.internal_translator.T("messages.level_up", loc, {
                        "mention": message.author.mention,
                        "new_level": result['new_level']
                    }),
                    color=Color.gold()
                )

                target_channel = message.channel
                if lev_cfg.notify_channel:
                    custom_chan = message.guild.get_channel(lev_cfg.notify_channel)
                    if isinstance(custom_chan, Messageable):
                        target_channel = custom_chan

                with contextlib.suppress(Forbidden):
                    await target_channel.send(embed=embed)

    @group.command(
        name="configure",
        description=app_commands.locale_str("command.leveling.configure.description"))
    @app_commands.default_permissions(administrator=True)
    async def configure_leveling(
        self,
        interaction: Interaction,
        multiplier: float | None = None,
        notify: bool | None = None,
        channel: TextChannel | None = None
    ):
        loc = interaction.guild.preferred_locale if interaction.guild else "en"
        await interaction.response.defer()

        embed = Embed()

        if not interaction.guild:
            embed.title = self.bot.internal_translator.T("error.embeds.guild_only.title", loc)
            embed.description = self.bot.internal_translator.T("error.embeds.guild_only.description", loc)
            return await interaction.followup.send(embed=embed)

        if not self.bot.guild_db:
            embed.title = self.bot.internal_translator.T("error.embeds.database_not_available.title", loc)
            embed.description = self.bot.internal_translator.T("error.embeds.database_not_available.description", loc)
            embed.timestamp = datetime.now(UTC)
            embed.color = Color.red()

            return interaction.followup.send(embed=embed)

        config = await self.bot.guild_db.get_config(interaction.guild.id)

        if multiplier is not None:
            config.leveling.xp_rate = max(0.1, min(multiplier, 5.0))

        if notify is not None:
            config.leveling.notify = notify

        if channel is not None:
            config.leveling.notify_channel = channel.id

        await self.bot.guild_db.update_config(interaction.guild.id, config)

        embed.title = self.bot.internal_translator.T("command.leveling.configure.embeds.default.title", loc)
        embed.description = self.bot.internal_translator.T("command.leveling.configure.embeds.default.description", loc)

        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(LevelingCog(bot))
