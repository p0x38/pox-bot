from collections import defaultdict
from datetime import datetime
import time
from typing import Optional

import aiomysql
from discord.ext import commands
from discord import AttachmentFlags, Color, Embed, Forbidden, Interaction, Message, TextChannel, app_commands
from pytz import UTC

from bot import PoxBot

from logger import logger
from src.models import AntiSpamFilter, FilterConfig, GlobalChatConfig, PhoneStatus, UserphoneConfig
from src.translator import translator_instance as i18n

class UserphoneCog(commands.Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot
        self.history = defaultdict(list)
    
    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if message.author.bot or not message.guild or not self.bot.guild_db:
            return
        
        config = await self.bot.guild_db.get_config(message.guild.id)
        
        global_feat = config.global_chat
        if global_feat.enabled and message.channel.id == global_feat.channel_id:
            if await self.check_antispam(message.author.id, config.filtering):
                await self.broadcast_global_message(message)
        
        phone_feat = config.userphone
        if phone_feat.status == PhoneStatus.in_call and message.channel.id == phone_feat.channel_id:
            if not phone_feat.current_partner_id: return
            
            partner_config = await self.bot.guild_db.get_config(phone_feat.current_partner_id)
            
            partner_channel = self.bot.get_channel(partner_config.userphone.channel_id) if partner_config.userphone.channel_id else None
            
            if partner_channel and isinstance(partner_channel, TextChannel):
                profile = await self.bot.user_db.get_full_profile(message.author.id) if self.bot.user_db else None
                name = profile.get("nickname") if profile else message.author.display_name
                
                await partner_channel.send(f"**{name}**: {message.content}")
    
    async def check_antispam(self, user_id: int, filtering_config: FilterConfig) -> bool:
        spam_filter = filtering_config.filters.get("anti_spam")
        
        if not isinstance(spam_filter, AntiSpamFilter) or not spam_filter.enabled:
            return True
        
        now = time.time()
        user_msgs = self.history[user_id]
        
        self.history[user_id] = [t for t in user_msgs if now - t < spam_filter.window_length]
        
        if len(self.history[user_id]) >= spam_filter.messages_per_window:
            return False
        
        self.history[user_id].append(now)
        return True
    
    async def broadcast_global_message(self, original: Message):
        if not original.guild: return
        profile = await self.bot.user_db.get_full_profile(original.author.id) if self.bot.user_db else None
        display_name = profile.get("nickname") if profile else original.author.display_name
        
        embed = Embed(description=original.content, color=Color.green())
        embed.set_author(name=display_name, icon_url=original.author.display_avatar.url)
        embed.set_footer(text=f"Sent from {original.guild.name if original.guild else "Unknown"}")
        
        for guild in self.bot.guilds:
            if guild.id == original.guild.id:
                continue
            
            config = await self.bot.guild_db.get_config(guild.id) if self.bot.guild_db else None
            if not config: continue
            
            global_feat = config.global_chat
            
            if global_feat.enabled and global_feat.channel_id:
                channel = guild.get_channel(global_feat.channel_id)
                if channel and isinstance(channel, TextChannel):
                    await channel.send(embed=embed)
    
    group = app_commands.Group(name="userphone", description=app_commands.locale_str("command.userphone.description"))
    
    @group.command(name="call", description=app_commands.locale_str("command.userphone.call.description"))
    async def call(self, interaction: Interaction):
        loc = interaction.guild.preferred_locale if interaction.guild else "en"
        await interaction.response.defer()
        
        embed = Embed()
        
        if not interaction.guild:
            embed.title = i18n.T("error.embeds.guild_only.title", loc)
            embed.description = i18n.T("error.embeds.guild_only.description", loc)
            return await interaction.followup.send(embed=embed)
        
        if not self.bot.guild_db:
            embed.title = i18n.T("error.embeds.database_not_available.title", loc)
            embed.description = i18n.T("error.embeds.database_not_available.description", loc)
            embed.timestamp = datetime.now(UTC)
            embed.color = Color.red()

            return await interaction.followup.send(embed=embed)
        
        guild_id = interaction.guild.id
        config = await self.bot.guild_db.get_config(guild_id)
        
        if config.userphone.status == PhoneStatus.in_call:
            embed.title = i18n.T("error.embeds.phone_in_call.title", loc)
            embed.description = i18n.T("error.embeds.phone_in_call.description", loc)
            embed.timestamp = datetime.now(UTC)
            embed.color = Color.red()

            return await interaction.followup.send(embed=embed)
        
        partner_id = await self.bot.guild_db.find_random_partner(guild_id)
        
        if partner_id:
            partner_config = await self.bot.guild_db.get_config(partner_id)
            
            config.userphone.status = PhoneStatus.in_call
            config.userphone.current_partner_id = partner_id
            
            partner_config.userphone.status = PhoneStatus.in_call
            partner_config.userphone.current_partner_id = guild_id
            
            await self.bot.guild_db.update_config(guild_id, config)
            await self.bot.guild_db.update_config(partner_id, partner_config)
            
            embed.title = i18n.T("command.userphone.call.embeds.paired.title", loc)
            embed.description = i18n.T("command.userphone.call.embeds.paired.description", loc)
            embed.timestamp = datetime.now(UTC)
            embed.color = Color.red()

            await interaction.followup.send(embed=embed)
        else:
            config.userphone.status = PhoneStatus.searching
            await self.bot.guild_db.update_config(guild_id, config)
            
            embed.title = i18n.T("command.userphone.call.embeds.searching.title", loc)
            embed.description = i18n.T("command.userphone.call.embeds.searching.description", loc)
            embed.timestamp = datetime.now(UTC)
            embed.color = Color.red()
            
            await interaction.followup.send(embed=embed)
        
    @group.command(name="hangup", description=app_commands.locale_str("command.userphone.hangup.description"))
    async def hangup(self, interaction: Interaction):
        loc = interaction.guild.preferred_locale if interaction.guild else "en"
        await interaction.response.defer()
        
        embed = Embed()
        
        if not interaction.guild:
            embed.title = i18n.T("error.embeds.guild_only.title", loc)
            embed.description = i18n.T("error.embeds.guild_only.description", loc)
            return await interaction.followup.send(embed=embed)
        
        if not self.bot.guild_db:
            embed.title = i18n.T("error.embeds.database_not_available.title", loc)
            embed.description = i18n.T("error.embeds.database_not_available.description", loc)
            embed.timestamp = datetime.now(UTC)
            embed.color = Color.red()

            return await interaction.followup.send(embed=embed)
        
        guild_id = interaction.guild.id
        config = await self.bot.guild_db.get_config(guild_id)
        
        if config.userphone.status != PhoneStatus.in_call:
            embed.title = i18n.T("error.embeds.not_in_call.title", loc)
            embed.description = i18n.T("error.embeds.not_in_call.description", loc)
            embed.timestamp = datetime.now(UTC)
            embed.color = Color.red()

            return await interaction.followup.send(embed=embed)
        
        partner_id = config.userphone.current_partner_id
        if partner_id is None:
            embed.title = i18n.T("error.embeds.not_in_call.title", loc)
            embed.description = i18n.T("error.embeds.not_in_call.description", loc)
            embed.timestamp = datetime.now(UTC)
            embed.color = Color.red()

            return await interaction.followup.send(embed=embed)

        partner_config = await self.bot.guild_db.get_config(partner_id)
        
        config.userphone.status = PhoneStatus.idle
        config.userphone.current_partner_id = None
        
        partner_config.userphone.status = PhoneStatus.idle
        partner_config.userphone.current_partner_id = None
        
        await self.bot.guild_db.update_config(guild_id, config)
        await self.bot.guild_db.update_config(partner_id, partner_config)
        
        await self.bot.guild_db.log_execution(guild_id, "userphone", interaction.user.id)
        
        embed.title = i18n.T("command.userphone.hangup.embeds.default.title", loc)
        embed.description = i18n.T("command.userphone.hangup.embeds.default.description", loc)
        embed.timestamp = datetime.now(UTC)
        embed.color = Color.red()
        
        await interaction.followup.send(embed=embed)
        
        partner_channel = self.bot.get_channel(partner_config.userphone.channel_id) if partner_config.userphone.channel_id else None
        if partner_channel and isinstance(partner_channel, TextChannel):
            await partner_channel.send("The other side hung up.")
    
    @group.command(name="globalchat", description=app_commands.locale_str("command.userphone.globalchat.description"))
    async def config_globalchat(self, interaction: Interaction, enabled: bool, channel: TextChannel | None = None):
        loc = interaction.guild.preferred_locale if interaction.guild else "en"
        await interaction.response.defer()
        
        embed = Embed()
        
        if not interaction.guild:
            embed.title = i18n.T("error.embeds.guild_only.title", loc)
            embed.description = i18n.T("error.embeds.guild_only.description", loc)
            return await interaction.followup.send(embed=embed)
        
        if not self.bot.guild_db:
            embed.title = i18n.T("error.embeds.database_not_available.title", loc)
            embed.description = i18n.T("error.embeds.database_not_available.description", loc)
            embed.timestamp = datetime.now(UTC)
            embed.color = Color.red()

            return await interaction.followup.send(embed=embed)
        
        guild_id = interaction.guild.id
        config = await self.bot.guild_db.get_config(guild_id)
        
        config.features['global_chat'] = GlobalChatConfig(
            enabled=enabled,
            channel_id=channel.id if channel else None,
            last_executor=interaction.user.id
        )
        
        await self.bot.guild_db.update_config(guild_id, config)
        
        embed.title = i18n.T("command.userphone.globalchat.embeds.default.title", loc)
        embed.description = i18n.T("command.userphone.globalchat.embeds.default.description", loc)
        embed.timestamp = datetime.now(UTC)
        embed.color = Color.green()
        
        await interaction.followup.send(embed=embed)
    
    @group.command(name="userphone", description=app_commands.locale_str("command.userphone.userphone.description"))
    async def config_userphone(self, interaction: Interaction, enabled: bool, channel: TextChannel | None = None):
        loc = interaction.guild.preferred_locale if interaction.guild else "en"
        await interaction.response.defer()
        
        embed = Embed()
        
        if not interaction.guild:
            embed.title = i18n.T("error.embeds.guild_only.title", loc)
            embed.description = i18n.T("error.embeds.guild_only.description", loc)
            return await interaction.followup.send(embed=embed)
        
        if not self.bot.guild_db:
            embed.title = i18n.T("error.embeds.database_not_available.title", loc)
            embed.description = i18n.T("error.embeds.database_not_available.description", loc)
            embed.timestamp = datetime.now(UTC)
            embed.color = Color.red()

            return await interaction.followup.send(embed=embed)
        
        guild_id = interaction.guild.id
        config = await self.bot.guild_db.get_config(guild_id)
        
        if config.userphone.status != PhoneStatus.idle:
            embed.title = i18n.T("error.embeds.need_hangup.title", loc)
            embed.description = i18n.T("error.embeds.need_hangup.description", loc)
            embed.timestamp = datetime.now(UTC)
            embed.color = Color.red()

            return await interaction.followup.send(embed=embed)
        
        config.features['userphone'] = UserphoneConfig(
            enabled=enabled,
            channel_id=channel.id if channel else None,
            status=PhoneStatus.idle,
            last_executor=interaction.user.id
        )
        
        await self.bot.guild_db.update_config(guild_id, config)
        
        embed.title = i18n.T("command.userphone.userphone.embeds.default.title", loc)
        embed.description = i18n.T("command.userphone.userphone.embeds.default.description", loc)
        embed.timestamp = datetime.now(UTC)
        embed.color = Color.green()
        
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(UserphoneCog(bot))