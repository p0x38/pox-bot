from discord import Interaction, app_commands


def is_bot_owner():
    async def predicate(interaction: Interaction) -> bool:
        if await interaction.client.is_owner(interaction.user):
            return True

        raise app_commands.AppCommandError("This command is only available for bot owner.")

    return app_commands.check(predicate)
