from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any

from openrouter import OpenRouter

from ..request_context import LLMRequestContext

if TYPE_CHECKING:
    from ....services.ai import LLMManager

from ....shared.abc.base_provider import BaseLLMProvider
from ....shared.exceptions.ai_error import InvalidQueryData


class OpenRouterStreamer(BaseLLMProvider):
    """Concrete implementation of BaseLLMProvider for OpenRouter API.

    Handles connection lifecycle, token streaming, and records initial
    Time-To-First-Token (TTFT) latency via the manager's metrics proxy.
    """

    def __init__(self, manager: 'LLMManager', api_key: str | None):
        """Initialize the OpenRouter streamer strategy.

        Args:
            manager (LLMManager): The parent LLM manager containing logger and metrics.
            api_key (str | None): Valid API key or None to let client fallback.
        """
        self.mgr = manager
        self.api_key = api_key

    async def stream_response(
        self,
        llm_model: str,
        query: Any,
        ctx: LLMRequestContext,
        base_labels: dict[str, str],
    ) -> AsyncGenerator[str, None]:
        """Request a streaming response from OpenRouter and yields text chunks.

        Args:
            llm_model (str): The model ID to use.
            query (Any): The payload to send.
            start_time (datetime): The timestamp when the original request initiated.
            base_labels (dict): Pre-configured telemetry labels for metrics routing.

        Returns:
            AsyncGenerator[str, None]: Text chunks streamed directly from the provider.
        """
        if not isinstance(query, list):
            raise InvalidQueryData()
        
        client = OpenRouter(api_key=self.api_key)

        thinking_logged = False
        generating_logged = False
        ttft_recorded = False
        try:
            self.mgr.logger.info(
                'Requesting response to OpenRouter at %s...',
                ctx.start_time.isoformat(),
            )
            response = await client.chat.send_async(
                model=llm_model,
                messages=query,
                stream=True,
            )

            async for chunk in response:
                if not thinking_logged:
                    thinking_logged = True
                    self.mgr.logger.info('LLM is thinking...')
                choice = chunk.choices[0] if chunk.choices else None
                content = getattr(choice.delta, "content", None) if choice else None
                if content:
                    if not ttft_recorded:
                        await self.mgr._record_metric(
                            name='bot_ai_ttft_seconds',
                            m_type='histogram',
                            value_or_amount=ctx.elapsed_seconds,
                            labels=base_labels,
                            description=(
                                'Time to first token (TTFT) '
                                'for LLM responses in seconds'
                            ),
                        )
                        ttft_recorded = True
                    if not generating_logged:
                        generating_logged = True
                        self.mgr.logger.info('LLM is generating response...')
                    yield content
        finally:
            if hasattr(client, "close"):
                await client.close()
            
            self.mgr.logger.debug('OpenRouter client successfully closed')
