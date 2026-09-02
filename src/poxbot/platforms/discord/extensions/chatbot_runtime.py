from __future__ import annotations

from discord import Interaction

from ....application import PoxBot
from .chatbot import ChatbotCog


def _clear_markov_runtime(cog: ChatbotCog) -> int:
    """Clear in-memory Markov models and dialogue memories.

    Persistent Markov data is intentionally left untouched. The next request
    will load the models and dialogue memories from their persistent stores.
    """
    cached_entries = len(cog.markov_models) + len(cog.markov_dialogues)

    cog.markov_models.clear()
    cog.markov_dialogues.clear()

    return cached_entries


if ChatbotCog.chatbot_group.get_command('reload') is None:

    @ChatbotCog.chatbot_group.command(
        name='reload',
        description='Reload the chatbot and Markov runtime state',
    )
    async def chatbot_reload(interaction: Interaction) -> None:
        cog = interaction.client.get_cog('ChatbotCog')

        if not isinstance(cog, ChatbotCog):
            await interaction.response.send_message(
                'The chatbot extension is not loaded.',
                ephemeral=True,
            )
            return

        cached_entries = _clear_markov_runtime(cog)

        await interaction.response.send_message(
            'Chatbot runtime state reloaded. '
            f'Cleared {cached_entries} cached Markov entr'
            f"{'y' if cached_entries == 1 else 'ies'}.",
            ephemeral=True,
        )


async def setup(bot: PoxBot) -> None:
    """Register runtime-only chatbot controls on the existing chatbot group."""
    del bot
