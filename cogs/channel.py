from typing import Optional, Union

from aiocache import cached
from discord import Color, Embed, Forbidden, Guild, TextChannel, Interaction, app_commands, VoiceChannel, CategoryChannel, StageChannel, ForumChannel
from discord.abc import GuildChannel
from discord.ext import commands

from bot import PoxBot
from logger import logger
import stuff

from src.translator import translator_instance

class ChannelCog(commands.Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot
    
    group = app_commands.Group(name="channel", description=app_commands.locale_str("A group for channels.", extras={"key": "command.channel.description"}))
    
    @group.command(name=app_commands.locale_str("slowmode", extras={"key": "command.channel.slowmode.name"}), description=app_commands.locale_str("Sets slowmode delay", extras={"key": "command.channel.slowmode.description"}))
    @app_commands.guild_only()
    async def set_slowmode_delay(self, interaction: Interaction, channel: Optional[TextChannel], seconds: app_commands.Range[int, 0, 21600]):
        loc = await self.bot.settings_db.get_locale(interaction) if self.bot.settings_db else interaction.locale
        embed = Embed(description=translator_instance.T("text.unknown", loc), color=Color.red())
        
        if not seconds: seconds = 0
        
        if not interaction.guild:
            embed.title = translator_instance.T("error.embed.guild_only.title", loc)
            embed.description = translator_instance.T("error.embed.guild_only.description", loc)
            return await interaction.response.send_message(embed=embed)
        
        await interaction.response.defer()
        
        if not channel:
            if interaction.channel_id:
                try:
                    retrieved_channel = self.bot.get_channel(interaction.channel_id)
                    if not isinstance(retrieved_channel, TextChannel):
                        raise TypeError(translator_instance.T("error.custom.unsupported_channel", loc))
                    
                    if not hasattr(retrieved_channel, "slowmode_delay"):
                        raise TypeError(translator_instance.T("error.custom.channel_has_no_slowmode_property", loc))
                    
                    channel = retrieved_channel
                except Exception as e:
                    embed.description = str(e)
                    return await interaction.followup.send(embed=embed)
            else:
                embed.description = translator_instance.T("error.embed.guild_only.description", loc)
                return await interaction.followup.send(embed=embed)
        
        try:
            if not hasattr(channel, "edit") or not hasattr(channel, "slowmode_delay"):
                embed.description = translator_instance.T("error.embed.unsupported_channel_slowmode.description", loc, {"channel": channel.mention})
                return await interaction.followup.send(embed=embed)
            
            if not (0 <= seconds <= 21600):
                embed.description = translator_instance.T("error.embed.slowmode_out_of_range.description", loc)
                return await interaction.followup.send(embed=embed)
            
            await channel.edit(slowmode_delay=seconds)
            
            success_embed = Embed(
                title=translator_instance.T("command.channel.slowmode.embeds.successful.title", loc),
                description=translator_instance.T("command.channel.slowmode.embeds.successful.description", loc, {"seconds": seconds, "mention": channel.mention}),
                color=Color.green()
            )
            
            await interaction.followup.send(embed=success_embed)
        except Forbidden:
            logger.error("Tried to edit slowmode, but bot doesn't have permission to change it.")
            embed.description = translator_instance.T("command.channel.slowmode.error.forbidden", loc)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            embed.description = translator_instance.T("error.exceptions.Unknown", loc, {"e": e})
            await interaction.followup.send(embed=embed)
    
    @group.command(name="info", description="Shows channel information.")
    @app_commands.guild_only()
    async def get_channel_info(self, interaction: Interaction, channel: GuildChannel):
        loc = await self.bot.settings_db.get_locale(interaction) if self.bot.settings_db else interaction.locale.value
        embed = Embed(description=translator_instance.T("text.unknown", loc), color=Color.red())
        
        if not interaction.guild:
            embed.title = translator_instance.T("error.embed.guild_only.title", loc)
            embed.description = translator_instance.T("error.embed.guild_only.description", loc)
            return await interaction.response.send_message(embed=embed)
        
        await interaction.response.defer()
        
        if channel:
            defrows = {
                'channel_name': channel.name,
                'channel_position': str(channel.position),
                'channel_type': str(channel.type),
                'channel_creation': channel.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                'channel_category': channel.category.name if channel.category else 'None'
            }
            exist = True
            extrarows = None
            
            if isinstance(channel, TextChannel):
                extrarows = {
                    'channel_slowmode': stuff.format_seconds(channel.slowmode_delay) if channel.slowmode_delay != 0 else "Disabled",
                    'channel_topic': channel.topic if channel.topic else "No topic specified",
                    'channel_nsfw': stuff.format_boolean(channel.nsfw),
                    'channel_threads': f"{len(channel.threads)} threads"
                }
            elif isinstance(channel, VoiceChannel):
                extrarows = {
                    'channel_nsfw': stuff.format_boolean(channel.nsfw),
                    'channel_bitrate': f"{channel.bitrate / 1000} kbps",
                    'channel_userlimit': f"{channel.user_limit} users",
                    'channel_slowmode': stuff.format_seconds(channel.slowmode_delay) if channel.slowmode_delay != 0 else "Disabled"
                }
            elif isinstance(channel, CategoryChannel):
                extrarows = {
                    'channel_nsfw': stuff.format_boolean(channel.nsfw),
                    'channel_channels': len(channel.channels)
                }
            elif isinstance(channel, StageChannel):
                extrarows = {
                    'channel_nsfw': stuff.format_boolean(channel.nsfw),
                    'channel_instance_running': stuff.format_boolean(True if channel.instance else False),
                    'channel_listeners': len(channel.members),
                    'channel_requesting_to_speak': len(channel.requesting_to_speak),
                    'channel_topic': channel.topic if channel.topic else "No topic specified",
                    'channel_userlimit': f"{channel.user_limit} users"
                }
            elif isinstance(channel, ForumChannel):
                extrarows = {
                    'channel_topic': channel.topic if channel.topic else "No topic specified",
                    'channel_threads': f"{len(channel.threads)} threads",
                    'channel_slowmode': stuff.format_seconds(channel.slowmode_delay) if channel.slowmode_delay != 0 else "Disabled",
                    'channel_nsfw': stuff.format_boolean(channel.nsfw),
                }
            else:
                exist = False
                embed.title = translator_instance.T("error.embed.unsupported_channel_type.title", loc)
                embed.description = translator_instance.T("error.embed.unsupported_channel_type.description", loc)
            
            if exist:
                embed.color = Color.blurple()
                embed.title = translator_instance.T("command.channel.info.embeds.default.title", loc, {"name": channel.name})
                embed.description = None
                rows_to_add = defrows
                if extrarows:
                    rows_to_add.update(extrarows)
                
                rows_to_add = translator_instance.translate_map(rows_to_add, loc)
                
                for name, value in rows_to_add.items():
                    embed.add_field(name=name, value=value, inline=True)
            
            return await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(ChannelCog(bot))