from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any

from pygent import Agent
from pygent.memory import ConversationMemory
from pygent.providers.openrouter import OpenRouterProvider
from pygent.types import Message

from ....shared.abc.base_provider import BaseLLMProvider
from ....shared.exceptions.ai_error import InvalidQueryData
from ..request_context import LLMRequestContext

if TYPE_CHECKING:
    from ....services.ai import LLMManager


class OpenRouterStreamer(BaseLLMProvider):
    """Pygent-backed OpenRouter provider adapter.

    Pygent owns provider communication and agent execution while this adapter
    preserves pox-bot's existing streaming-manager interface.
    """

    def __init__(
        self,
        manager: 'LLMManager',
        api_key: str | None,
    ) -> None:
        self.mgr = manager
        self.api_key = api_key

    async def stream_response(
        self,
        llm_model: str,
        query: Any,
        ctx: LLMRequestContext,
        base_labels: dict[str, str],
    ) -> AsyncGenerator[str, None]:
        """Generate a response through Pygent.

        The surrounding manager retains its historical async-generator API.
        Pygent's current OpenRouter provider performs a complete request, so
        the final response is yielded as one chunk for now.
        """
        if not isinstance(query, list) or not query:
            raise InvalidQueryData()

        try:
            messages = [Message.model_validate(item) for item in query]
        except Exception as exc:
            raise InvalidQueryData() from exc

        last_message = messages[-1]
        history = messages[:-1]

        memory = ConversationMemory(conversation_id="pox-bot")
        if history:
            memory.seed(history)

        provider = OpenRouterProvider(
            llm_model,
            api_key=self.api_key,
            app_name="pox-bot",
        )
        agent = Agent(
            provider,
            max_iterations=4,
            max_tool_calls=8,
            total_timeout=60.0,
            memory=memory,
        )

        try:
            response = await agent.run(last_message)
        finally:
            await provider.aclose()

        if response.text:
            await self.mgr._record_metric(
                name='bot_ai_ttft_seconds',
                m_type='histogram',
                value_or_amount=ctx.elapsed_seconds,
                labels=base_labels,
                description='Time to first token (TTFT) for LLM responses in seconds',
            )
            self.mgr.logger.info('LLM generated response through Pygent.')
            yield response.text

        await asyncio.sleep(0)
