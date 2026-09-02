from typing import cast

import pytest

from poxbot.application.bot import PoxBot
from poxbot.features.ai.manager import LLMManager, LLMProviderType
from poxbot.features.ai.providers.openrouter import OpenRouterStreamer
from poxbot.shared.exceptions.ai_error import MissingInput


class DummyBot:
    def __init__(self):
        self.metrics = None


def test_manager_is_exposed_from_llm_processor_package():
    manager = LLMManager(cast(PoxBot, DummyBot()))

    assert manager.preferred == LLMProviderType.OPEN_ROUTER
    assert isinstance(
        manager._get_provider_strategy(LLMProviderType.OPEN_ROUTER.value),
        OpenRouterStreamer,
    )


@pytest.mark.asyncio
async def test_generate_response_requires_complete_input():
    manager = LLMManager(cast(PoxBot, DummyBot()))

    with pytest.raises(MissingInput):
        async with manager.generate_response({'provider': 'openrouter'}):
            pass
