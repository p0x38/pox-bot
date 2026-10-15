from discord import Interaction, app_commands


class ModerationCommandTree(app_commands.CommandTree):
    async def interaction_check(self, interaction: Interaction) -> bool:
        checker = getattr(interaction.client, 'is_bot_banned', None)

        if checker is None or not await checker(interaction.user.id):
            return True

        translator = getattr(
            interaction.client,
            'internal_translator',
            None
        )
        key = 'error.custom.user_restricted_from_using_commands'

        message = (
            translator.T(key, interaction.locale.value)
            if translator is not None
            else key
        )

        if message == key:
            message = "You are restricted from using this bot."

        await interaction.response.send_message(
            message,
            ephemeral=True,
        )
        return False
