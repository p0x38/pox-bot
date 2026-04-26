import json
import os
from typing import Optional
import aiofiles
from discord import Color, Embed, Interaction, Member, TextChannel, app_commands
from discord.ext import commands
from logger import logger
from src.translator import translator_instance as i18n

from bot import PoxBot

class WelcomeCog(commands.Cog):
    group = app_commands.Group(name="welcome", description=app_commands.locale_str("A group for WelcomeCog", message="command.welcome.description"))

    def __init__(self, bot):
        self.bot: PoxBot = bot
        self.data = {}
        self.file_path = os.path.join(self.bot.root_path, "data/welcome.json")
    
    async def save(self):
        data_to_save = {str(k): v for k, v in self.data.items()}

        try:
            async with aiofiles.open(self.file_path, mode='w+', encoding='utf-8') as f:
                await f.write(json.dumps(data_to_save, indent=4))
            logger.info("welcome.json Saved")
        except Exception as e:
            logger.exception(f"Error saving welcome.json asynchronously: {e}")
    
    async def load(self):
        if not os.path.exists(self.file_path):
            logger.warning("welcome.json not found. Starting with empty...")
            return {}
        
        try:
            async with aiofiles.open(self.file_path, mode='r', encoding='utf-8') as f:
                content = await f.read()
            
            raw_data = json.loads(content)
            self.data = {int(k): v for k, v in raw_data.items()}
            logger.info("welcome.json loaded")
        except json.JSONDecodeError:
            logger.error("Error decoding JSON. Starting with empty data.")
            self.data = {}
    
    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("Loading database...")
        await self.load()
    
    async def cog_unload(self) -> None:
        logger.info("Saving data")
        await self.save()
    
    @commands.Cog.listener()
    async def on_member_join(self, member: Member):
        is_enabled2 = self.data.get(member.guild.id)

        if is_enabled2:
            is_enabled = is_enabled2.get('welcome', 0)
            rule_channel_id = is_enabled2.get('rules', 0)

            if is_enabled != 0:
                await self.send_message("join", is_enabled, member, rule_channel_id)
    
    @commands.Cog.listener()
    async def on_member_leave(self, member: Member):
        is_enabled2 = self.data.get(member.guild.id)

        if is_enabled2:
            is_enabled = is_enabled2.get('welcome', 0)

            if is_enabled != 0:
                await self.send_message("left", is_enabled, member)
    
    async def send_message(self, state: str, channel_id: int, member: Member, rules_id: Optional[int] = None):
        channel = self.bot.get_channel(channel_id)
        if channel is None: return
        if not isinstance(channel, TextChannel): return

        embed = Embed()

        guild = channel.guild
        loc = i18n._normalize_locale(guild.preferred_locale)

        try:
            if state == "join":
                title = i18n.T("command.welcome.embeds.join.title", loc, {"guild": guild.name})
                desc = i18n.T("command.welcome.embeds.join.description", loc, {
                    "mention": member.mention,
                    "rules_mention": f"<#{rules_id}" if rules_id != 0 else ""
                })

                if rules_id == 0:
                    desc = i18n.T("command.welcome.embeds.join.description_no_rules", loc, {"mention": member.mention})
                
                embed.title = title
                embed.description = desc
                embed.color = Color.brand_green()

                footer_text = i18n.T("command.welcome.embeds.join.footer", loc, {"count": guild.member_count})
                embed.set_footer(text=footer_text)
            elif state == "left":
                title = i18n.T("command.welcome.embeds.left.title", loc, {"guild": guild.name, "display": member.display_name})
                desc = i18n.T("command.welcome.embeds.left.description", loc, {
                    "display": member.display_name
                })

                embed.title = title
                embed.description = desc
                embed.color = Color.brand_red()

            await channel.send(content=member.mention, embed=embed)
        except Exception as e:
            logger.exception(i18n.T("error.exceptions.Unknown", loc, {"e": e}))
            return
    
    @group.command(name="set_channel", description=app_commands.locale_str("Set channel to send join / leave message.", message="command.welcome.set_channel.description"))
    @app_commands.guild_only()
    async def set_channel(self, interaction: Interaction, channel: Optional[TextChannel]):
        loc = await self.bot.settings_db.get_locale(interaction) if self.bot.settings_db else interaction.locale
        embed = Embed(color=Color.blurple())

        if interaction.guild is None:
            embed.description = i18n.T("error.custom.guild_only", loc)
            embed.color = Color.red()
            return await interaction.response.send_message(embed=embed)

        await interaction.response.defer()

        self.data.setdefault(interaction.guild.id, {})

        if channel is None:
            self.data[interaction.guild.id]['welcome'] = 0
            await self.save()
            embed.description = i18n.T("command.welcome.set_channel.embeds.disabled.description", loc)
            return await interaction.followup.send(f"Welcome channel has been disabled.")
        else:
            self.data[interaction.guild.id]['welcome'] = channel.id
            await self.save()
            embed.description = i18n.T("command.welcome.set_channel.embeds.changed.description", loc, {"target_mention": channel.mention})
            return await interaction.followup.send(embed=embed)
    
    @group.command(name="test", description=app_commands.locale_str("Run a test for welcome channel", message="command.welcome.test.description"))
    @app_commands.guild_only()
    async def test_channel(self, interaction: Interaction):
        loc = await self.bot.settings_db.get_locale(interaction) if self.bot.settings_db else interaction.locale
        embed = Embed(color=Color.blurple())
        
        if interaction.guild is None:
            embed.description = i18n.T("error.custom.guild_only", loc)
            embed.color = Color.red()
            return await interaction.response.send_message(embed=embed)

        await interaction.response.defer()

        is_enabled2 = self.data.get(interaction.guild.id)

        if not is_enabled2:
            embed.description = i18n.T("error.embeds.welcome_channel_not_enabled.description", loc)
            embed.title = i18n.T("error.embeds.welcome_channel_not_enabled.title", loc)
            embed.color = Color.red()
            return await interaction.response.send_message(embed=embed)

        is_enabled = is_enabled2.get('welcome', 0)
        rule_channel_id = is_enabled2.get('rules', 0)

        if is_enabled != 0:
            await self.send_message("join", is_enabled, interaction.guild.me, rule_channel_id)
            embed.description = i18n.T("command.welcome.test.embeds.sent.description", loc)
            return await interaction.followup.send(embed=embed)
        else:
            embed.description = i18n.T("command.welcome.test.embeds.unconfigured.description", loc)
            return await interaction.followup.send(embed=embed)
    
    @group.command(name="set_rules_channel", description=app_commands.locale_str("Sets rule channel for adding link in it.", message="command.welcome.set_rules_channel.description"))
    @app_commands.guild_only()
    async def set_rule_channel(self, interaction: Interaction, channel: TextChannel):
        loc = await self.bot.settings_db.get_locale(interaction) if self.bot.settings_db else interaction.locale
        embed = Embed(color=Color.blurple())
        
        if interaction.guild is None:
            embed.description = i18n.T("error.custom.guild_only", loc)
            embed.color = Color.red()
            return await interaction.response.send_message(embed=embed)

        await interaction.response.defer()

        self.data.setdefault(interaction.guild.id, {})

        if channel is None:
            self.data[interaction.guild.id]['rules'] = 0
            await self.save()
            embed.description = i18n.T("command.welcome.set_rules_channel.embeds.disabled.description", loc)
            return await interaction.followup.send(embed=embed)
        else:
            self.data[interaction.guild.id]['rules'] = channel.id
            await self.save()
            embed.description = i18n.T("command.welcome.set_rules_channel.embeds.success.description", loc)
            return await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(WelcomeCog(bot))