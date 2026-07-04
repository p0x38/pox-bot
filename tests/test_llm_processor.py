
import pytest

from src.exceptions.ai_error import MissingInput
from src.llm_processor import LLMManager, LLMProviderType
from src.llm_processor.providers.openrouter import OpenRouterStreamer


class DummyBot:
    def __init__(self):
        self.metrics = None


def test_manager_is_exposed_from_llm_processor_package():
    manager = LLMManager(DummyBot())

    assert manager.preferred == LLMProviderType.OPEN_ROUTER
    assert isinstance(
        manager._get_provider_strategy(LLMProviderType.OPEN_ROUTER.value),
        OpenRouterStreamer,
    )


@pytest.mark.asyncio
async def test_generate_response_requires_complete_input():
    manager = LLMManager(DummyBot())

    with pytest.raises(MissingInput):
        async for _ in manager.generate_response({'provider': 'openrouter'}):
            pass
