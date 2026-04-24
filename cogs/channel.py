from typing import Optional, Union

from aiocache import cached
from discord import Color, Embed, Forbidden, Guild, TextChannel, Interaction, app_commands, VoiceChannel, CategoryChannel, StageChannel, ForumChannel
from discord.abc import GuildChannel
from discord.ext import commands

from bot import PoxBot
from logger import logger
import stuff

class ChannelGroup(commands.Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot
    
    group = app_commands.Group(name="channel", description="A group for channel.")
    
    @group.command(name="slowmode", description="Sets slowmode delay")
    @app_commands.guild_only()
    async def set_slowmode_delay(self, interaction: Interaction, channel: Optional[TextChannel], seconds: app_commands.Range[int, 0, 21600]):
        embed = Embed(title="Unknown error", color=Color.red())
        
        if not seconds: seconds = 0
        
        if not interaction.guild:
            embed.title = "Invalid run context"
            embed.description = "You must have to run the command in guild."
            return await interaction.response.send_message(embed=embed)
        
        await interaction.response.defer()
        
        if not channel:
            if interaction.channel_id:
                try:
                    retrieved_channel = self.bot.get_channel(interaction.channel_id)
                    if not isinstance(retrieved_channel, TextChannel):
                        raise TypeError("The channel isn't supported by bot")
                    
                    if not hasattr(retrieved_channel, "slowmode_delay"):
                        raise TypeError("Channel has no property to set slowmode delay")
                    
                    channel = retrieved_channel
                except Exception as e:
                    embed.description = str(e)
                    return await interaction.followup.send(embed=embed)
            else:
                embed.description = "Interaction seems ran in non-guild"
                return await interaction.followup.send(embed=embed)
        
        try:
            if not hasattr(channel, "edit") or not hasattr(channel, "slowmode_delay"):
                embed.description = f"{channel.mention} does not support slowmode."
                return await interaction.followup.send(embed=embed)
            
            if not (0 <= seconds <= 21600):
                embed.description = "Slowmode delay must be between 0 and 21600 seconds."
                return await interaction.followup.send(embed=embed)
            
            await channel.edit(slowmode_delay=seconds)
            
            success_embed = Embed(
                title="Slowmode updated",
                description=f"Successfully set slowmode to **{seconds}** for {channel.mention}.",
                color=Color.green()
            )
            
            await interaction.followup.send(embed=success_embed)
        except Forbidden:
            logger.error("Tried to edit slowmode, but bot doesn't have permission to change it.")
            embed.description = "I do not have the **Manage Channels** permission to do that."
            await interaction.followup.send(embed=embed)
        except Exception as e:
            embed.description = f"An unexpected error occured: {e}"
            await interaction.followup.send(embed=embed)
    
    @group.command(name="info", description="Shows channel information.")
    @app_commands.guild_only()
    async def get_channel_info(self, interaction: Interaction, channel: GuildChannel):
        embed = Embed(title="Unknown channel", color=Color.red(), description="Unknown channel.")
        
        if not interaction.guild:
            embed.title = "Invalid run context"
            embed.description = "You've ran the command on non-guild. try to run the command in guild."
            return await interaction.response.send_message(embed=embed)
        
        await interaction.response.defer()
        
        if channel:
            defrows = {
                'Channel Name': channel.name,
                'Channel Position': str(channel.position),
                'Channel Type': str(channel.type),
                'Created at': channel.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                'Category': channel.category.name if channel.category else 'None'
            }
            exist = True
            extrarows = None
            
            if isinstance(channel, TextChannel):
                extrarows = {
                    'Slowmode Delay': stuff.format_seconds(channel.slowmode_delay) if channel.slowmode_delay != 0 else "Disabled",
                    'Channel Topic': channel.topic if channel.topic else "No topic specified",
                    'Is NSFW': stuff.format_boolean(channel.nsfw),
                    'Thread count': f"{len(channel.threads)} threads"
                }
            elif isinstance(channel, VoiceChannel):
                extrarows = {
                    'Is NSFW': stuff.format_boolean(channel.nsfw),
                    'Bitrate': f"{channel.bitrate / 1000} kbps",
                    'User limit': f"{channel.user_limit} users",
                    'Slowmode Delay': stuff.format_seconds(channel.slowmode_delay) if channel.slowmode_delay != 0 else "Disabled"
                }
            elif isinstance(channel, CategoryChannel):
                extrarows = {
                    'Is NSFW': stuff.format_boolean(channel.nsfw),
                    'Channels': len(channel.channels)
                }
            elif isinstance(channel, StageChannel):
                extrarows = {
                    'Is NSFW': stuff.format_boolean(channel.nsfw),
                    'Is Instance running': stuff.format_boolean(True if channel.instance else False),
                    'Members listening': len(channel.members),
                    'Members who requested to speak': len(channel.requesting_to_speak),
                    'Channel Topic': channel.topic if channel.topic else "No topic specified",
                    'User limit': f"{channel.user_limit} users"
                }
            elif isinstance(channel, ForumChannel):
                extrarows = {
                    'Channel Topic': channel.topic if channel.topic else "No topic specified",
                    'Thread count': f"{len(channel.threads)} threads",
                    'Slowmode Delay': stuff.format_seconds(channel.slowmode_delay) if channel.slowmode_delay != 0 else "Disabled",
                    'Is NSFW': stuff.format_boolean(channel.nsfw),
                }
            else:
                exist = False
                embed.title = "Unknown channel type"
                embed.description = "You've chose a channel that is not able to analyze."
            
            if exist:
                embed.color = Color.blurple()
                embed.title = f"Information of {channel.name}"
                embed.description = None
                rows_to_add = defrows
                if extrarows:
                    rows_to_add.update(extrarows)
                
                for name, value in rows_to_add.items():
                    embed.add_field(name=name, value=value, inline=True)
            
            return await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(ChannelGroup(bot))