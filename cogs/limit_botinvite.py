import asyncio
import platform
import time
from discord import ButtonStyle, Color, Embed, Guild, Interaction, SelectOption, app_commands
import discord
from discord.ext import commands, tasks
from discord.ui import Select
import distro
from datetime import datetime, timezone
import psutil
import pytz

from bot import PoxBot
from cogs.chatbot import ChatbotCog
from logger import logger
from stuff import get_formatted_from_seconds
import stuff
    
class BotInvitationLimiterCog(commands.Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot
        self.max_servers = self.bot.bot_servers_limit
        self.is_over_limit = False
        
        self.guild_watchdog.start()
    
    async def cog_unload(self) -> None:
        self.guild_watchdog.cancel()
    
    @tasks.loop(minutes=5.0)
    async def guild_watchdog(self):
        if len(self.bot.guilds) > self.max_servers:
            fallback_date = datetime.min.replace(tzinfo=timezone.utc)
            
            sorted_guilds = sorted(self.bot.guilds, key=lambda g: g.me.joined_at or fallback_date, reverse=True)            
            for guild in sorted_guilds:
                if len(self.bot.guilds) <= self.max_servers: break
                
                logger.info(f"Watchdog pruning: leaving {guild.name}")
                await guild.leave()
    
    @guild_watchdog.before_loop
    async def before_watchdog(self):
        await self.bot.wait_until_ready()
    
    @commands.Cog.listener()
    async def on_guild_join(self, guild: Guild):
        if len(self.bot.guilds) > self.max_servers:
            logger.warning(f"Joined {guild.name}, but limit reached ({len(self.bot.guilds)}/{self.max_servers}). Leaving...")
            
            try:
                if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
                    await guild.system_channel.send(
                        "** Server limit reached **\n"
                        "To maintain hardware stability and discord compliance, "
                        f"this bot is capped at {self.max_servers} servers. Leaving now..."
                    )
            except: pass
            
            await guild.leave()
    
async def setup(bot):
    await bot.add_cog(BotInvitationLimiterCog(bot))