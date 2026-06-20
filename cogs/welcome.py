from datetime import datetime

from discord import Color, Embed, Interaction, Member, TextChannel, User, app_commands
from discord.ext import commands
from pytz import UTC

from bot import PoxBot
from logger import logger
from src.models import WelcomeChannels, WelcomeConfig
from src.translator import translator_instance as i18n


class WelcomeCog(commands.Cog):
    def __init__(self, bot: PoxBot):
        self.bot = bot
        
    group = app_commands.Group(name="welcome", description=app_commands.locale_str("command.welcome.description"))
    
    def format_user_as_text(self, user: User | Member):
        if user.name == user.display_name:
            return user.display_name
        else:
            return f"{user.display_name} ({user.name})"
    
    async def send_message(self, member: Member, leaving: bool = False):
        if not self.bot.guild_db: return
        if not await self.bot.guild_db.get_config(member.guild.id): return
        
        guild_settings = await self.bot.guild_db.get_config(member.guild.id)
        if not guild_settings.welcome or not guild_settings.welcome.enabled: return
        if not isinstance(guild_settings.welcome, WelcomeConfig): return
        
        target_channel_id = 0
        
        match (leaving):
            case True:
                target_channel_id = (
                    guild_settings.welcome.channels.leave
                    if (
                        guild_settings.welcome.channels.leave and 
                        guild_settings.welcome.channels.leave != 0
                    )
                    else (
                        guild_settings.welcome.channels.join
                        if (
                            guild_settings.welcome.channels.join and 
                            guild_settings.welcome.channels.join != 0
                        )
                        else 0
                    )
                )
            case False:
                target_channel_id = (
                    guild_settings.welcome.channels.join
                    if (
                        guild_settings.welcome.channels.join and 
                        guild_settings.welcome.channels.join != 0
                    )
                    else 0
                )
        
        if target_channel_id == 0 or target_channel_id == None: return
        
        target_channel = self.bot.get_channel(target_channel_id)
        if not isinstance(target_channel, TextChannel): return
        
        try:
            embed = Embed()
            rows_to_add = {
                "user_id": member.id,
                "user_name": self.format_user_as_text(member),
                "user_bot": "Yes" if member.bot else "No",
                "user_creation": member.created_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")
            }
            
            if leaving:
                rows_to_add.update({
                    "user_join": member.joined_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S") if member.joined_at else "Unknown",
                })
            
            for name, value in rows_to_add.items():
                embed.add_field(name=name, value=value, inline=False)
            
            await target_channel.send(embed=embed)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Could not send welcome message: {e}")
    
    @commands.Cog.listener()
    async def on_member_join(self, member: Member):
        await self.send_message(member)
    
    @commands.Cog.listener()
    async def on_member_remove(self, member: Member):
        await self.send_message(member, leaving=True)
    
    async def interaction_check(self, interaction) -> bool:
        loc = interaction.guild.preferred_locale if interaction.guild else "en"
        
        if not self.bot.guild_db:
            embed = Embed(
                title=i18n.T("error.embeds.database_not_available.title", loc),
                description=i18n.T("error.embeds.database_not_available.description", loc),
                timestamp=datetime.now(UTC),
                color=Color.red()
            )
            
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        if not interaction.guild:
            embed = Embed(
                title=i18n.T("error.embeds.guild_only.title", loc),
                description=i18n.T("error.embeds.guild_only.description", loc),
                timestamp=datetime.now(UTC),
                color=Color.red()
            )
            
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        return True
    
    @group.command(name="toggle", description=app_commands.locale_str("command.welcome.toggle.description"))
    @app_commands.describe(enabled=app_commands.locale_str("command.welcome.toggle.parameters.enabled"))
    async def toggle_welcome(self, interaction: Interaction, enabled: bool = False):
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
        guild_settings = await self.bot.guild_db.get_config(guild_id)
        
        if guild_settings.features and "welcome" in guild_settings.features and isinstance(guild_settings.features["welcome"], WelcomeConfig):
            guild_settings.features["welcome"].enabled = enabled
        else:
            guild_settings.features["welcome"] = WelcomeConfig(enabled=enabled)
        
        await self.bot.guild_db.update_config(guild_id, guild_settings)
        
        await self.bot.guild_db.log_execution(guild_id, "welcome", interaction.user.id)
        
        embed.title = i18n.T("command.welcome.toggle.embeds.default.title", loc)
        embed.description = i18n.T("command.welcome.toggle.embeds.default.description", loc, {"toggle": "enabled" if enabled else "disabled"})
        
        return await interaction.followup.send(embed=embed)
    
    @group.command(name="joinchannel", description=app_commands.locale_str("command.welcome.joinchannel.description"))
    @app_commands.describe(channel=app_commands.locale_str("command.welcome.joinchannel.parameters.channel"))
    async def set_joinchannel(self, interaction: Interaction, channel: TextChannel):
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
        guild_settings = await self.bot.guild_db.get_config(guild_id)
        
        if guild_settings.features and "welcome" in guild_settings.features and isinstance(guild_settings.features["welcome"], WelcomeConfig):
            guild_settings.features["welcome"].channels.join = channel.id
        else:
            guild_settings.features["welcome"] = WelcomeConfig(channels=WelcomeChannels(join=channel.id))
        
        await self.bot.guild_db.update_config(guild_id, guild_settings)
        
        await self.bot.guild_db.log_execution(guild_id, "welcome", interaction.user.id)
        
        embed.title = i18n.T("command.welcome.joinchannel.embeds.default.title", loc)
        embed.description = i18n.T("command.welcome.joinchannel.embeds.default.description", loc, channel=channel.mention)
        
        return await interaction.followup.send(embed=embed)
    
    @group.command(name="leavechannel", description=app_commands.locale_str("command.welcome.leavechannel.description"))
    @app_commands.describe(channel=app_commands.locale_str("command.welcome.leavechannel.parameters.channel"))
    async def set_leavechannel(self, interaction: Interaction, channel: TextChannel):
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
        guild_settings = await self.bot.guild_db.get_config(guild_id)
        
        if guild_settings.features and "welcome" in guild_settings.features and isinstance(guild_settings.features["welcome"], WelcomeConfig):
            guild_settings.features["welcome"].channels.leave = channel.id
        else:
            guild_settings.features["welcome"] = WelcomeConfig(channels=WelcomeChannels(join=channel.id))
        
        await self.bot.guild_db.update_config(guild_id, guild_settings)
        
        await self.bot.guild_db.log_execution(guild_id, "welcome", interaction.user.id)
        
        embed.title = i18n.T("command.welcome.leavechannel.embeds.default.title", loc)
        embed.description = i18n.T("command.welcome.leavechannel.embeds.default.description", loc, channel=channel.mention)
        
        return await interaction.followup.send(embed=embed)
    
async def setup(bot: PoxBot):
    await bot.add_cog(WelcomeCog(bot))