from __future__ import annotations

from poxbot.features.markov.dialogue import MarkovDialogueMemory
from poxbot.features.markov.model import MarkovModel, MarkovModelKey
from poxbot.platforms.discord.extensions.chatbot import ChatbotCog
from poxbot.platforms.discord.extensions.chatbot_runtime import (
    _clear_markov_runtime,  # ruff: ignore[import-private-name]
)


def test_clear_markov_runtime_clears_only_runtime_caches() -> None:
    cog = object.__new__(ChatbotCog)

    key = MarkovModelKey.global_model()

    cog.markov_models = {
        key: MarkovModel(),
    }
    cog.markov_dialogues = {
        key: MarkovDialogueMemory(),
    }

    cleared = _clear_markov_runtime(cog)

    assert cleared == 2
    assert cog.markov_models == {}
    assert cog.markov_dialogues == {}
