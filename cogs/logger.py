
from discord import (
    DMChannel,
    Guild,
    Interaction,
    InteractionType,
    Member,
    User,
)
from discord.ext import commands

from bot import PoxBot
from logger import logger


def format_user_as_text(user: User | Member):
    if user.name == user.display_name:
        return user.display_name
    else:
        return f"{user.display_name} (username: {user.name})"
    
class LoggerCog(commands.Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot
    
    @commands.Cog.listener()
    async def on_interaction(self, interaction: Interaction):
        match (interaction.type):
            case InteractionType.application_command:
                command_name = "Unknown command"
                guild_name = "Unknown"
                channel_name = "unknown"
                
                if interaction.command and interaction.command.qualified_name.strip():
                    command_name = "/" + interaction.command.qualified_name.strip()
                
                if interaction.guild and interaction.guild.name.strip():
                    guild_name = interaction.guild.name.strip()
                
                if interaction.channel:
                    if isinstance(interaction.channel, DMChannel):
                        channel_name = "DM Channel"
                    else:
                        if interaction.channel.guild and interaction.channel.guild.name.strip():
                            guild_name = interaction.channel.guild.name
                        channel_name = interaction.channel.name
                
                logger.info(
                    r'"{}" used command "{}" at "{}"'.format(
                        format_user_as_text(interaction.user),
                        command_name,
                        f"{guild_name} - #{channel_name}" if interaction.guild else f"{channel_name}"
                    )
                )
            case _:
                pass
    
    @commands.Cog.listener()
    async def on_guild_join(self, guild: Guild):
        logger.info(f"The bot has been invited to \"{guild.name}\" ({guild.id}).")
    
    @commands.Cog.listener()
    async def on_guild_remove(self, guild: Guild):
        logger.info(f"The bot has been removed from \"{guild.name}\" ({guild.id}).")
    
    @commands.Cog.listener()
    async def on_member_join(self, member: Member):
        logger.info(f"Member {member.display_name} ({member.id}) joined to {member.guild.name} ({member.guild.id}).")
        
    @commands.Cog.listener()
    async def on_member_remove(self, member: Member):
        logger.info(f"Member {member.display_name} ({member.id}) left from {member.guild.name} ({member.guild.id}).")

async def setup(bot):
    await bot.add_cog(LoggerCog(bot))