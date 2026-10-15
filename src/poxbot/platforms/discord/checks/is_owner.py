from typing import cast

from discord import Interaction, app_commands
from discord.ext import commands


def is_bot_owner():
    async def predicate(interaction: Interaction) -> bool:
        bot = cast(commands.AutoShardedBot, interaction.client)

        if await bot.is_owner(interaction.user):
            return True

        raise app_commands.AppCommandError(
            'This command is only available for bot owner.',
        )

    return app_commands.check(predicate)
