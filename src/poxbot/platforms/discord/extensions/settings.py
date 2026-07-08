from discord import Color, Embed, Interaction, app_commands, ui
from discord.ext import commands

from ....application import PoxBot
from ....persistence.database import SettingsDatabase
from ....persistence.models import SettingsData


class LocalizedSettingsView(ui.View):
    def __init__(
        self,
        bot: PoxBot,
        user_id: int,
        initial_data: SettingsData,
        db_manager: SettingsDatabase,
    ):
        super().__init__(timeout=180)
        self.bot = bot
        self.user_id = user_id
        self.data = initial_data
        self.db = db_manager

        self.build_ui()

    def build_ui(self):
        self.clear_items()
        self.add_language_menu()

    def add_language_menu(self):
        options = self.bot.i18n_manager.get_select_options(self.data.locale)

        select_menu = ui.Select(placeholder='Select Language', options=options, row=0)

        select_menu.callback = self.on_language_select
        self.add_item(select_menu)

    async def on_language_select(self, interaction: Interaction):
        if interaction.data and 'values' in interaction.data:
            selected_locale = interaction.data['values'][0]
        else:
            selected_locale = self.data.locale

        if isinstance(selected_locale, list):
            selected_locale = selected_locale[0]

        normalized = self.bot.internal_translator._normalize_locale(selected_locale)
        self.data.locale = normalized

        await self.db.set_settings(self.user_id, self.data)

        self.build_ui()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    def create_embed(self) -> Embed:
        loc = self.data.locale

        color_hex = self.data.embed_color.replace('#', '')
        color_int = int(color_hex, 16) if color_hex else 0x2B2D31

        embed = Embed(
            title=self.bot.internal_translator.T('settings.title', loc),
            color=color_int,
        )

        info = self.bot.i18n_manager.lang_info.get(loc, {'name': loc, 'emoji': '🌐'})
        emoji = info.get('emoji', '🌐')
        name = info.get('display', info.get('name', 'Unknown'))
        lang_display = f'{emoji} {name}'

        embed.description = (
            f'{self.bot.internal_translator.T("settings.header_description", loc)}\n\n'
            f'**{
                self.bot.internal_translator.T(
                    "settings.fields.locale", loc, {"lang_code": lang_display}
                )
            }\n\n'
            f'**{
                self.bot.internal_translator.T(
                    "settings.fields.embed_color", loc, {"hex": self.data.embed_color}
                )
            }'
        )

        embed.set_footer(text=f'{self.bot.internal_translator.T("settings.page", loc)}')
        return embed


class SettingsCog(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot: PoxBot = bot

    @app_commands.command(
        name='settings',
        description=app_commands.locale_str('command.settings.description'),
    )
    async def show_settings(self, interaction: Interaction):
        loc = (
            await self.bot.database.settings.get_locale(interaction)
            if self.bot.database.settings
            else interaction.locale
        )
        embed = Embed(color=Color.red())

        if not self.bot.database.settings:
            embed.description = self.bot.internal_translator.T(
                'error.embeds.no_connection',
                loc,
            )
            return await interaction.response.send_message(embed=embed)

        data = await self.bot.database.settings.get_settings(interaction.user.id)

        self.bot.logger.debug('BEFORE DISPLAY: %s %s', data.locale, type(data.locale))
        view = LocalizedSettingsView(
            self.bot,
            interaction.user.id,
            data,
            self.bot.database.settings,
        )

        await interaction.response.send_message(
            embed=view.create_embed(),
            view=view,
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(SettingsCog(bot))
