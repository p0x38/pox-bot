from dataclasses import asdict, dataclass
import json
from typing import Optional

import asyncpg
import discord
from discord import Color, app_commands
from discord.ext import commands
from discord import Embed, Interaction, ui
from bot import PoxBot
from src.translator import translator_instance as i18n
from src.translator import translation_manager
from src.database.modules import SettingsDatabase

from models import SettingsData

class LocalizedSettingsView(ui.View):
    def __init__(self, user_id: int, initial_data: SettingsData, db_manager: SettingsDatabase):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.data = initial_data
        self.db = db_manager
        
        self.build_ui()
    
    def build_ui(self):
        self.clear_items()
        self.add_language_menu()
    
    def add_language_menu(self):
        options = translation_manager.get_select_options(self.data.locale)
        
        select_menu = ui.Select(
            placeholder="Select Language",
            options=options,
            row=0
        )
        
        select_menu.callback = self.on_language_select
        self.add_item(select_menu)
    
    async def on_language_select(self, interaction: Interaction):
        if interaction.data and "values" in interaction.data:
            selected_locale = interaction.data["values"][0]
        else:
            selected_locale = self.data.locale
        
        if isinstance(selected_locale, list):
            selected_locale = selected_locale[0]
        
        normalized = i18n._normalize_locale(selected_locale)
        self.data.locale = normalized
        
        await self.db.set_settings(self.user_id, self.data)
        
        self.build_ui()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)
    
    def create_embed(self) -> Embed:
        loc = self.data.locale
        
        color_hex = self.data.embed_color.replace("#", "")
        color_int = int(color_hex, 16) if color_hex else 0x2b2d31

        embed = Embed(
            title=i18n.T("settings.title", loc),
            color=color_int
        )

        info = translation_manager.lang_info.get(loc, {"name": loc, "emoji": "🌐"})
        lang_display = f"{info['emoji']} {info['name']}"
        
        embed.description = (
            f"{i18n.T('settings.header_description', loc)}\n\n"
            f"**{i18n.T('settings.fields.locale', loc, {"lang_code": lang_display})}\n\n"
            f"**{i18n.T('settings.fields.embed_color', loc, {"hex": self.data.embed_color})}"
        )
        
        embed.set_footer(text=f"{i18n.T('settings.page', loc)}")
        return embed

class SettingsCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot: PoxBot = bot
    
    @app_commands.command(name="settings", description=app_commands.locale_str("Shows user settings.", message="command.settings.description"))
    async def show_settings(self, interaction: Interaction):
        loc = await self.bot.settings_db.get_locale(interaction) if self.bot.settings_db else interaction.locale
        embed = Embed(color=Color.red())
        
        if not self.bot.settings_db:
            embed.description = i18n.T('error.embeds.no_connection', loc)
            return await interaction.response.send_message(embed=embed)
        
        data = await self.bot.settings_db.get_settings(interaction.user.id)
        
        print("BEFORE DISPLAY:", data.locale, type(data.locale))
        view = LocalizedSettingsView(interaction.user.id, data, self.bot.settings_db)
        
        await interaction.response.send_message(
            embed=view.create_embed(),
            view=view,
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(SettingsCog(bot))