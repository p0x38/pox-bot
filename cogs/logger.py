from typing import Union

from discord import ButtonStyle, Color, DMChannel, Embed, Guild, Interaction, InteractionType, Member, Message, SelectOption, User, app_commands
from discord.ext import commands, tasks

from bot import PoxBot
from cogs.chatbot import ChatbotCog
from logger import logger
import stuff

def format_user_as_text(user: Union[User, Member]):
    return "{} ({})".format(user.display_name, user.name)
    
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
                        channel_name = interaction.channel.name
                
                logger.info(
                    r'"{}" used command "{}" on "{}"'.format(
                        format_user_as_text(interaction.user),
                        command_name,
                        f"{guild_name} - {channel_name}" if interaction.guild else f"{channel_name}"
                    )
                )
            case _:
                pass
    
    @commands.Cog.listener()
    async def on_guild_join(self, guild: Guild):
        logger.info("The bot has been invited to {} ({}).".format(guild.name, guild.id))
    
    @commands.Cog.listener()
    async def on_guild_remove(self, guild: Guild):
        logger.info("The bot has been removed from {} ({}).".format(guild.name, guild.id))
    
    @commands.Cog.listener()
    async def on_member_join(self, member: Member):
        logger.info("Member {} ({}) joined to {} ({}).".format(
            member.display_name,
            member.id,
            member.guild.name,
            member.guild.id
        ))
        
    @commands.Cog.listener()
    async def on_member_remove(self, member: Member):
        logger.info("Member {} ({}) left from {} ({}).".format(
            member.display_name,
            member.id,
            member.guild.name,
            member.guild.id
        ))

async def setup(bot):
    await bot.add_cog(LoggerCog(bot))