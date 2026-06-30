from discord import Guild, Member, User
from discord.ext import commands

from src.core.bot import PoxBot
from src.logger_factory.logger import setup_logger


class LoggerCog(commands.Cog):
    def __init__(self, bot: PoxBot):
        self.logger = setup_logger(__name__, "LoggerCog")
        self.bot = bot

    def format_guild_info(self, guild: Guild):
        return f"{guild.name} ({guild.id})"

    def format_user(self, user: User | Member):
        return f"{user.display_name} ({user.id})"

    @commands.Cog.listener()
    async def on_guild_join(self, guild: Guild):
        self.logger.info(
            "The bot has been invited to %s",
            self.format_guild_info(guild),
        )

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: Guild):
        self.logger.info(
            "The bot has been removed from %s",
            self.format_guild_info(guild),
        )

    @commands.Cog.listener()
    async def on_member_join(self, member: Member):
        self.logger.info(
            "%s has joined to %s",
            self.format_user(member),
            self.format_guild_info(member.guild),
        )

    @commands.Cog.listener()
    async def on_member_remove(self, member: Member):
        self.logger.info(
            "%s has left from %s",
            self.format_user(member),
            self.format_guild_info(member.guild),
        )

    @commands.Cog.listener()
    async def on_member_ban(self, guild: Guild, user: User | Member):
        self.logger.info(
            "%s has banned from %s",
            self.format_user(user),
            self.format_guild_info(guild),
        )


async def setup(bot: PoxBot):
    await bot.add_cog(LoggerCog(bot))
