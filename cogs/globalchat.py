from typing import Optional

import aiomysql
from discord.ext import commands
from discord import AttachmentFlags, Color, Embed, Forbidden, Interaction, Message, TextChannel, app_commands

from bot import PoxBot

from logger import logger

class GlobalChatCog(commands.Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot
        self.channels = set()
    
    async def cog_load(self):
        if not self.bot.mysql:
            logger.error("Error: MySQL connection not found.")
            return
        
        if isinstance(self.bot.mysql, aiomysql.Connection):
            async with self.bot.mysql.cursor() as cur:
                await cur.execute("SELECT channel FROM globalchannels")
                rows = await cur.fetchall()
                self.channels = {row[0] for row in rows}
    
    group = app_commands.Group(name="global", description="Nice")
    
    @group.command(name="setglobal")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def set_globalchannel(self, interaction: Interaction, channel: Optional[TextChannel] = None):
        if not isinstance(interaction.channel, TextChannel):
            return interaction.response.send_message("You must've be in Guild text channel.")
        
        await interaction.response.defer()
        
        if not channel:
            channel = interaction.channel
        
        if isinstance(self.bot.mysql, aiomysql.Connection):
            async with self.bot.mysql.cursor() as cur:
                await cur.execute("INSERT IGNORE INTO global_channels (channel, guild) VALUES (%s, %s)", (channel.id, channel.guild.id))
            self.channels.add(channel.id)
            await interaction.followup.send("# Global chat linked to {}.".format(channel.mention))
        else:
            await interaction.followup.send("Failed to integrate: Connection not available")
    
    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if message.author.bot: return
        
        context = await self.bot.get_context(message)
        if context.valid: return
        
        if message.channel.id in self.channels:
            await self.broadcast(message)
    
    async def broadcast(self, message: Message):
        filtered_attachments = []
        for v in message.attachments:
            if not v.content_type: continue
            if not (v.content_type.startswith("image") or v.content_type.startswith("video")): continue
            filtered_attachments.append(v)
        
        for id in self.channels:
            if id == message.channel.id: continue
            channel = self.bot.get_channel(id)
            if channel:
                try:
                    if isinstance(channel, TextChannel) and channel.permissions_for(channel.guild.me).send_messages:
                        await channel.send(f"**{message.author.name}**: {message.content}")
                except Forbidden:
                    pass
        
async def setup(bot):
    await bot.add_cog(GlobalChatCog(bot))