from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any

from pygent import Agent
from pygent.memory import ConversationMemory
from pygent.providers.ollama import OllamaProvider
from pygent.types import Message

from ....shared.abc.base_provider import BaseLLMProvider
from ....shared.exceptions.ai_error import InvalidQueryData
from ..request_context import LLMRequestContext

if TYPE_CHECKING:
    from ....services.ai import LLMManager


class OllamaStreamer(BaseLLMProvider):
    """Pygent-backed Ollama provider adapter."""

    def __init__(
        self,
        manager: LLMManager,
        host: str | None,
    ) -> None:
        self.mgr = manager
        self.host = host

    async def stream_response(
        self,
        llm_model: str,
        query: Any,
        ctx: LLMRequestContext,
        base_labels: dict[str, str],
    ) -> AsyncGenerator[str, None]:
        """Generate a response through a local or remote Ollama instance."""
        if not isinstance(query, list) or not query:
            raise InvalidQueryData()

        try:
            messages = [Message.model_validate(item) for item in query]
        except Exception as exc:
            raise InvalidQueryData() from exc

        last_message = messages[-1]
        history = messages[:-1]

        memory = ConversationMemory(conversation_id='pox-bot')
        if history:
            memory.seed(history)

        provider = OllamaProvider(
            llm_model,
            host=self.host,
        )
        agent = Agent(
            provider,
            max_iterations=4,
            max_tool_calls=8,
            total_timeout=60.0,
            memory=memory,
        )

        response = await agent.run(last_message)

        if response.text:
            await self.mgr._record_metric(
                name='bot_llm_response_latency_seconds',
                m_type='histogram',
                value_or_amount=ctx.elapsed_seconds,
                labels=base_labels,
                description='Total latency for LLM responses in seconds',
            )
            self.mgr.logger.info(
                'LLM generated response through Pygent Ollama (%s).',
                llm_model,
            )
            yield response.text
