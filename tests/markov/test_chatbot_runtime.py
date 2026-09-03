from __future__ import annotations

from typing import Any, cast

from poxbot.platforms.discord.extensions.chatbot import ChatbotCog
from poxbot.platforms.discord.extensions.chatbot_runtime import _clear_markov_runtime


def test_clear_markov_runtime_clears_only_runtime_caches() -> None:
    cog = cast(Any, object.__new__(ChatbotCog))
    cog.markov_models = {'model': object()}
    cog.markov_dialogues = {'dialogue': object()}

    cleared = _clear_markov_runtime(cog)

    assert cleared == 2
    assert cog.markov_models == {}
    assert cog.markov_dialogues == {}
