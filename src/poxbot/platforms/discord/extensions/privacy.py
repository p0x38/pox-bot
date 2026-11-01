from io import BytesIO

import orjson
from discord import (
    ButtonStyle,
    File,
    Interaction,
    app_commands,
    ui,
)
from discord.errors import HTTPException
from discord.ext import commands

from ....application import PoxBot
from ....services.privacy import PrivacyService


class PrivacyDeleteView(ui.View):
    confirmation_interaction: Interaction | None

    def __init__(
        self,
        bot: PoxBot,
        privacy: PrivacyService,
        owner_id: int,
        locale: str,
    ) -> None:
        super().__init__(timeout=60)

        self.bot = bot
        self.privacy = privacy
        self.owner_id = owner_id
        self.locale = locale

        self.processing = False
        self.confirmation_interaction = None

        for item in self.children:
            if not isinstance(item, ui.Button):
                continue

            if item.label == 'Confirm deletion':
                item.label = bot.internal_translator.T(
                    'command.privacy.delete.buttons.confirm',
                    locale,
                )

            elif item.label == 'Cancel':
                item.label = bot.internal_translator.T(
                    'command.privacy.delete.buttons.cancel',
                    locale,
                )

    def _disable_buttons(self) -> None:
        """Disable every button in this view."""
        for item in self.children:
            if isinstance(item, ui.Button):
                item.disabled = True

    async def interaction_check(
        self,
        interaction: Interaction,
    ) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                self.bot.internal_translator.T(
                    'command.privacy.delete.unauthorized',
                    self.locale,
                ),
                ephemeral=True,
            )
            return False

        return True

    async def on_timeout(self) -> None:
        interaction = self.confirmation_interaction

        if interaction is None:
            return

        try:
            await interaction.edit_original_response(
                content=self.bot.internal_translator.T(
                    'command.privacy.delete.expired',
                    self.locale,
                ),
                view=None,
            )

        except HTTPException:
            self.bot.logger.debug(
                'Could not update expired privacy confirmation.',
            )

    @ui.button(
        label='Confirm deletion',
        style=ButtonStyle.danger,
    )
    async def confirm(
        self,
        interaction: Interaction,
        button: ui.Button,
    ) -> None:
        if self.processing:
            await interaction.response.send_message(
                self.bot.internal_translator.T(
                    'command.privacy.delete.processing',
                    self.locale,
                ),
                ephemeral=True,
            )
            return

        self.processing = True
        self._disable_buttons()

        # Acknowledge the component interaction and disable its buttons.
        # This updates the existing confirmation message.
        await interaction.response.edit_message(
            content=self.bot.internal_translator.T(
                'command.privacy.delete.processing',
                self.locale,
            ),
            view=self,
        )

        try:
            report = await self.privacy.delete_user_data(
                self.owner_id,
            )

        except Exception:
            self.bot.logger.exception(
                'Failed to delete privacy data for user %s',
                self.owner_id,
            )

            await interaction.edit_original_response(
                content=self.bot.internal_translator.T(
                    'command.privacy.delete.failed',
                    self.locale,
                ),
                view=None,
            )

            self.stop()
            return

        deleted_count = sum(report['deleted'].values())
        anonymized_count = sum(report['anonymized'].values())
        retained_count = sum(report['retained'].values())

        await interaction.edit_original_response(
            content=self.bot.internal_translator.T(
                'command.privacy.delete.success',
                self.locale,
                {
                    'deleted': deleted_count,
                    'anonymized': anonymized_count,
                    'retained': retained_count,
                },
            ),
            view=None,
        )

        self.stop()

    @ui.button(
        label='Cancel',
        style=ButtonStyle.secondary,
    )
    async def cancel(
        self,
        interaction: Interaction,
        button: ui.Button,
    ) -> None:
        self._disable_buttons()

        await interaction.response.edit_message(
            content=self.bot.internal_translator.T(
                'command.privacy.delete.cancelled',
                self.locale,
            ),
            view=None,
        )

        self.stop()


class PrivacyCog(commands.Cog):
    def __init__(self, bot: PoxBot) -> None:
        self.bot = bot
        self.privacy = PrivacyService(bot.database)

    group = app_commands.Group(
        name='privacy',
        description=app_commands.locale_str(
            'command.privacy.description',
        ),
        allowed_contexts=app_commands.AppCommandContext(
            guild=True,
            dm_channel=True,
            private_channel=True,
        ),
    )

    @group.command(
        name='export',
        description=app_commands.locale_str(
            'command.privacy.export.description',
        ),
    )
    async def export_user_data(
        self,
        interaction: Interaction,
    ) -> None:
        loc = str(await self.bot.get_locale(interaction))

        await interaction.response.defer(
            thinking=True,
            ephemeral=True,
        )

        try:
            data = await self.privacy.export_user_data(
                interaction.user.id,
            )

            payload = orjson.dumps(
                data,
                option=(
                    orjson.OPT_INDENT_2
                    | orjson.OPT_SORT_KEYS
                ),
            )

            export_file = File(
                fp=BytesIO(payload),
                filename='poxbot-data-export.json',
            )

            await interaction.followup.send(
                content=self.bot.internal_translator.T(
                    'command.privacy.export.success',
                    loc,
                ),
                file=export_file,
                ephemeral=True,
            )

        except Exception:
            self.bot.logger.exception(
                'Failed to export privacy data for user %s',
                interaction.user.id,
            )

            await interaction.followup.send(
                content=self.bot.internal_translator.T(
                    'command.privacy.export.failed',
                    loc,
                ),
                ephemeral=True,
            )

    @group.command(
        name='delete',
        description=app_commands.locale_str(
            'command.privacy.delete.description',
        ),
    )
    async def delete_user_data(
        self,
        interaction: Interaction,
    ) -> None:
        loc = str(await self.bot.get_locale(interaction))
    
        view = PrivacyDeleteView(
            bot=self.bot,
            privacy=self.privacy,
            owner_id=interaction.user.id,
            locale=loc,
        )
    
        # Keep the original interaction so on_timeout() can edit
        # the ephemeral confirmation response.
        view.confirmation_interaction = interaction
    
        await interaction.response.send_message(
            content=self.bot.internal_translator.T(
                'command.privacy.delete.confirmation',
                loc,
            ),
            view=view,
            ephemeral=True,
        )


async def setup(bot: PoxBot) -> None:
    await bot.add_cog(PrivacyCog(bot))
