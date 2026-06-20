import re
import time
import unicodedata
from collections import defaultdict
from datetime import datetime
from typing import cast

import tldextract
from discord import (
    Color,
    Embed,
    Forbidden,
    HTTPException,
    Interaction,
    Message,
    NotFound,
    TextChannel,
    app_commands,
)
from discord.ext import commands
from openai.types.moderation_multi_modal_input_param import (
    ModerationMultiModalInputParam,
)
from pytz import UTC

from bot import PoxBot
from logger import logger
from src.models import (
    AntiSpamFilter,
    FilterConfig,
    GlobalChatConfig,
    PhoneStatus,
    UserphoneConfig,
)
from src.translator import translator_instance as i18n


class UserphoneCog(commands.Cog):
    def __init__(self, bot):
        self.bot: PoxBot = bot
        self.history = defaultdict(list)
        self.censored_words = [
            r"(?:https?://)?discord\.gg\/[a-zA-Z0-9]+"
        ]
        self.whitelisted_urls = []
    
    @commands.Cog.listener()
    async def on_message(self, message: Message):
        if message.author.bot or not message.guild or not self.bot.guild_db:
            return
        
        config = await self.bot.guild_db.get_config(message.guild.id)
        
        global_feat = config.global_chat
        if global_feat.enabled and message.channel.id == global_feat.channel_id and await self.check_antispam(message.author.id, config.filtering):
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
    
    async def censor_urls(self, text: str):
        text = unicodedata.normalize("NFKC", text)
        
        text = re.sub(r'[\u200b-\u200f\uFEFF\u202a-\u202e]', '', text)
        
        found = self.bot.url_extrator.find_urls(
            text,
            only_unique=True,
            check_dns=False,
            get_indices=True,
            with_schema_only=True
        )
        
        for item in reversed(found):
            if isinstance(item, str):
                is_whitelisted = any(w in item for w in self.whitelisted_urls)
                
                if not is_whitelisted:
                    text = text.replace(item, "[URL]")
            else:
                url, (start, end) = item
                
                ext = tldextract.extract(url)
                domain = f"{ext.domain}.{ext.suffix}"
                
                if domain not in self.whitelisted_urls:
                    text = text[:start] + "[URL]" + text[end:]
        
        return text
    
    async def get_moderation_warning(self, flagged_data: dict, locale: str):
        flagged = [cat for cat, val in flagged_data.items() if val]
        
        descriptions = []
        for cat in flagged:
            key = f"texts.moderation.categories.{cat}"
            descriptions.append(i18n.T(key, locale))
        
        if len(descriptions) == 1:
            combined = i18n.T("text.moderation.moderation.format.single", locale, {
                "content": descriptions[0]
            })
        elif len(descriptions) == 2:
            combined = i18n.T("text.moderation.moderation.format.two", locale, {
                "first": descriptions[0],
                "last": descriptions[1]
            })
        else:
            combined = i18n.T("text.moderation.moderation.format.multiple", locale, {
                "list": ", ".join(descriptions[:-1]),
                "last": descriptions[-1]
            })
        
        prefix = i18n.T("text.moderation.flagged_message", locale, {
            "categories": combined
        })
        return prefix
    
    async def check_content(self, content: str, image_urls: list[str]) -> tuple[bool, dict | None]:
        try:
            payload: list[ModerationMultiModalInputParam] = [{"type": "text", "text": content}]
            for url in image_urls:
                payload.append({"type": "image_url", "image_url": {"url": url}})
            
            response = self.bot.openai_client.moderations.create(input=cast(list[ModerationMultiModalInputParam], payload))
            result = response.results[0]
            
            if result.flagged:
                return False, result.categories.to_dict()
            return True, None
        except Exception as e:
            logger.exception(e)
            return False, {"unknown": True}
    
    async def is_text_sendable(self, message: Message):
        if message.guild and self.bot.profanity_filter.is_profane(message.content):
                return False
            
        for word in self.censored_words:
            if re.search(word, message.content):
                return False
        
        return True
    
    async def broadcast_global_message(self, original: Message):
        if not original.guild: return
        if not await self.is_text_sendable(original): return
        
        profile = await self.bot.user_db.get_full_profile(original.author.id) if self.bot.user_db else None
        display_name = profile.get("nickname") if profile else original.author.display_name
        
        description_text = original.content.replace("@everyone", "@\u200beveryone").replace("@here", "@\u200bhere")
        
        if not description_text:
            if original.attachments:
                description_text = f"User sent {len(original.attachments)} attachment(s)."
            else:
                return
        
        embed = Embed(
            description=await self.censor_urls(description_text),
            color=Color.green(),
            timestamp=original.created_at
        )
        embed.set_author(name=display_name, icon_url=original.author.display_avatar.url)
        embed.set_footer(text=f"Sent from {original.guild.name if original.guild else "Unknown"}")
                    
        if not embed.description:
            if original.attachments:
                embed.description = i18n.T("command.globalchat.texts.including_attachments_no_text", original.guild.preferred_locale, count=len(original.attachments))
            else:
                return
        else:
            if original.attachments:
                embed.description += f"\n\n ({i18n.T("command.globalchat.texts.including_attachments", original.guild.preferred_locale, count=len(original.attachments))})"
        
        image_urls = []
        for attachment in original.attachments:
            if not attachment.content_type: continue
            
            if not attachment.content_type.startswith(("image", "video")): continue
            
            image_urls.append(attachment.url)
        
        """is_clean, categories = await self.check_content(description_text, image_urls)
        if not is_clean and categories:
            warning = await self.get_moderation_warning(categories, original.guild.preferred_locale.language_code)
            embed.description = f"{warning}"
            embed.color = Color.red()"""
        
        for guild in self.bot.guilds:
            if guild.id == original.guild.id:
                continue
            
            config = await self.bot.guild_db.get_config(guild.id) if self.bot.guild_db else None
            if not config: continue
            
            global_feat = config.global_chat
            
            if global_feat.enabled and global_feat.channel_id:
                channel = guild.get_channel(global_feat.channel_id)
                if channel and isinstance(channel, TextChannel):
                    has_permission = channel.permissions_for(guild.me).send_messages
                    if not has_permission: continue
                    
                    files = []
                    
                    if True:
                        for attachment in original.attachments:
                            if not attachment.content_type: continue

                            if not attachment.content_type.startswith(("image", "video")): continue

                            try:
                                files.append(await attachment.to_file(
                                    spoiler=attachment.is_spoiler(),
                                ))
                            except (HTTPException, Forbidden, NotFound):
                                continue
                        
                    await channel.send(embed=embed, files=files)
    
    group = app_commands.Group(name="userphone", description=app_commands.locale_str("command.userphone.description"))
    globalchat_group = app_commands.Group(name="globalchat", description=app_commands.locale_str("command.globalchat.description"))
    
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
    
    @globalchat_group.command(name="toggle", description=app_commands.locale_str("command.globalchat.toggle.description"))
    @app_commands.describe(
        enabled=app_commands.locale_str("command.globalchat.toggle.parameters.enabled")
    )
    async def enable_globalchat_feature(self, interaction: Interaction, enabled: bool):
        loc = interaction.guild.preferred_locale if interaction.guild else "en"
        await interaction.response.defer()
        
        embed = Embed(color=Color.red(), timestamp=datetime.now(UTC))
        
        if not interaction.guild:
            embed.title = i18n.T("error.embeds.guild_only.title", loc)
            embed.description = i18n.T("error.embeds.guild_only.description", loc)
            return await interaction.followup.send(embed=embed)
        
        if not self.bot.guild_db:
            embed.title = i18n.T("error.embeds.database_not_available.title", loc)
            embed.description = i18n.T("error.embeds.database_not_available.description", loc)
            return await interaction.followup.send(embed=embed)
        
        guild_id = interaction.guild.id
        config = await self.bot.guild_db.get_config(guild_id)
        
        if config.features and "global_chat" in config.features and isinstance(config.features["global_chat"], GlobalChatConfig):
            config.features["global_chat"].enabled = enabled
        else:
            embed.title = i18n.T("error.embeds.feature_not_available.title", loc)
            embed.description = i18n.T("error.embeds.feature_not_available.description", loc)
            return await interaction.followup.send(embed=embed)
        
        await self.bot.guild_db.update_config(guild_id, config)
        
        await self.bot.guild_db.log_execution(guild_id, "userphone", interaction.user.id)
        
        embed.title = i18n.T("command.globalchat.toggle.embeds.default.title", loc)
        embed.description = i18n.T("command.globalchat.toggle.embeds.default.description", loc, {"enabled": "enabled" if enabled else "disabled"})
        
        await interaction.followup.send(embed=embed)
    
    @globalchat_group.command(name="setchannel", description=app_commands.locale_str("command.globalchat.setchannel.description"))
    @app_commands.describe(channel=app_commands.locale_str("command.globalchat.setchannel.parameters.channel"))
    async def set_globalchat_channel(self, interaction: Interaction, channel: TextChannel):
        loc = interaction.guild.preferred_locale if interaction.guild else "en"
        await interaction.response.defer()
        
        embed = Embed(color=Color.red(), timestamp=datetime.now(UTC))
        
        if not interaction.guild:
            embed.title = i18n.T("error.embeds.guild_only.title", loc)
            embed.description = i18n.T("error.embeds.guild_only.description", loc)
            return await interaction.followup.send(embed=embed)
        
        if not self.bot.guild_db:
            embed.title = i18n.T("error.embeds.database_not_available.title", loc)
            embed.description = i18n.T("error.embeds.database_not_available.description", loc)
            return await interaction.followup.send(embed=embed)
        
        guild_id = interaction.guild.id
        config = await self.bot.guild_db.get_config(guild_id)
        
        if config.features and "global_chat" in config.features and isinstance(config.features["global_chat"], GlobalChatConfig):
            config.features["global_chat"].channel_id = channel.id
        else:
            config.features["global_chat"] = GlobalChatConfig(channel_id=channel.id)
        
        await self.bot.guild_db.update_config(guild_id, config)
        
        await self.bot.guild_db.log_execution(guild_id, "userphone", interaction.user.id)
        
        embed.title = i18n.T("command.globalchat.setchannel.embeds.default.title", loc)
        embed.description = i18n.T("command.globalchat.setchannel.embeds.default.description", loc, {"channel": channel.mention})
        
        await interaction.followup.send(embed=embed)
        
    @globalchat_group.command(name="silentmode", description=app_commands.locale_str("command.globalchat.silentmode.description"))
    @app_commands.describe(toggle=app_commands.locale_str("command.globalchat.silentmode.parameters.toggle"))
    async def set_globalchat_silent_mode(self, interaction: Interaction, toggle: bool):
        loc = interaction.guild.preferred_locale if interaction.guild else "en"
        await interaction.response.defer()
        
        embed = Embed(color=Color.red(), timestamp=datetime.now(UTC))
        
        if not interaction.guild:
            embed.title = i18n.T("error.embeds.guild_only.title", loc)
            embed.description = i18n.T("error.embeds.guild_only.description", loc)
            return await interaction.followup.send(embed=embed)
        
        if not self.bot.guild_db:
            embed.title = i18n.T("error.embeds.database_not_available.title", loc)
            embed.description = i18n.T("error.embeds.database_not_available.description", loc)
            return await interaction.followup.send(embed=embed)
        
        guild_id = interaction.guild.id
        config = await self.bot.guild_db.get_config(guild_id)
        
        if config.features and "global_chat" in config.features and isinstance(config.features["global_chat"], GlobalChatConfig):
            config.features["global_chat"].silent = toggle
        else:
            config.features["global_chat"] = GlobalChatConfig(silent=toggle)
        
        await self.bot.guild_db.update_config(guild_id, config)
        
        await self.bot.guild_db.log_execution(guild_id, "userphone", interaction.user.id)
        
        embed.title = i18n.T("command.globalchat.silentmode.embeds.default.title", loc)
        embed.description = i18n.T("command.globalchat.silentmode.embeds.default.description", loc, {"toggle": "on" if toggle else "off"})
        
        await interaction.followup.send(embed=embed)
    
    """
    @group.command(name="globalchat", description=app_commands.locale_str("command.userphone.globalchat.description"))
    @app_commands.describe(
        enabled=app_commands.locale_str("command.userphone.globalchat.parameters.enabled"),
        channel=app_commands.locale_str("command.userphone.globalchat.parameters.channel"),
        silent_mode=app_commands.locale_str("command.userphone.globalchat.parameters.silent_mode")
    )
    async def config_globalchat(self, interaction: Interaction, enabled: bool, channel: TextChannel | None = None, silent_mode: bool = False):
        loc = interaction.guild.preferred_locale if interaction.guild else "en"
        await interaction.response.defer()
        
        if silent_mode is None:
            silent_mode = False
        
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
        
        if not channel:
            if isinstance(interaction.channel, TextChannel):
                channel = interaction.channel
            else:
                embed.title = i18n.T("error.embeds.channel_required.title", loc)
                embed.description = i18n.T("error.embeds.channel_required.description", loc)
                embed.timestamp = datetime.now(UTC)
                embed.color = Color.red()

                return await interaction.followup.send(embed=embed)
        
        permission = channel.permissions_for(interaction.guild.me)
        if not permission.send_messages and not permission.manage_messages:
            embed.title = i18n.T("error.embeds.missing_permission_global_chat.title", loc)
            embed.description = i18n.T("error.embeds.missing_permission_global_chat.description", loc)
            embed.timestamp = datetime.now(UTC)
            embed.color = Color.red()

            return await interaction.followup.send(embed=embed)
        
        guild_id = interaction.guild.id
        config = await self.bot.guild_db.get_config(guild_id)
        
        config.features['global_chat'] = GlobalChatConfig(
            enabled=enabled,
            channel_id=channel.id if channel else None,
            last_executor=interaction.user.id,
            silent=silent_mode
        )
        
        await self.bot.guild_db.update_config(guild_id, config)
        
        embed.title = i18n.T("command.userphone.globalchat.embeds.default.title", loc)
        embed.description = i18n.T("command.userphone.globalchat.embeds.default.description", loc)
        embed.timestamp = datetime.now(UTC)
        embed.color = Color.green()
        
        await interaction.followup.send(embed=embed)
    
    @group.command(name="change_globalchat_channel", description=app_commands.locale_str("command.userphone.change_globalchat_channel.description"))
    @app_commands.describe(channel=app_commands.locale_str("command.userphone.change_globalchat_channel.parameters.channel"))
    async def change_globalchat_channel(self, interaction: Interaction, channel: TextChannel):
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
        
        guild_features = config.features
        global_chat_feature = guild_features.get('global_chat')
        
        if global_chat_feature and isinstance(global_chat_feature, GlobalChatConfig):
            global_chat_feature.channel_id = channel.id
            config.features['global_chat'] = global_chat_feature
            await self.bot.guild_db.update_config(guild_id, config)
        else:
            embed.title = i18n.T("error.embeds.global_chat_not_enabled.title", loc)
            embed.description = i18n.T("error.embeds.global_chat_not_enabled.description", loc)
            embed.timestamp = datetime.now(UTC)
            embed.color = Color.red()

            return await interaction.followup.send(embed=embed)
        
        embed.title = i18n.T("command.userphone.change_globalchat_channel.embeds.default.title", loc)
        embed.description = i18n.T("command.userphone.change_globalchat_channel.embeds.default.description", loc)
        embed.timestamp = datetime.now(UTC)
        embed.color = Color.green()
        
        await interaction.followup.send(embed=embed)
    
    @group.command(name="silent_globalchat", description=app_commands.locale_str("command.userphone.silent_globalchat.description"))
    @app_commands.describe(toggle=app_commands.locale_str("command.userphone.silent_globalchat.parameters.toggle"))
    async def set_silent_mode_for_globalchat(self, interaction: Interaction, toggle: bool):
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
        
        if isinstance(config.features['global_chat'], GlobalChatConfig):
            config.features['global_chat'].silent = toggle
        
        await self.bot.guild_db.update_config(guild_id, config)
        
        embed.title = i18n.T("command.userphone.silent_globalchat.embeds.default.title", loc)
        embed.description = i18n.T("command.userphone.silent_globalchat.embeds.default.description", loc)
        embed.timestamp = datetime.now(UTC)
        embed.color = Color.green()
        
        await interaction.followup.send(embed=embed)
    """
    
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