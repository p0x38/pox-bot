from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Any

from ...features.ai.request_context import LLMRequestContext


class BaseLLMProvider(ABC):
    """Abstract base class representing a unified AI/LLM Provider.

    Every concrete provider strategy (e.g., OpenRouter, Gemini, OpenAI) must
    inherit from this class and implement the streaming response interface.
    """

    @abstractmethod
    def stream_response(
        self,
        llm_model: str,
        query: Any,
        ctx: LLMRequestContext,
        base_labels: dict[str, str],
    ) -> AsyncGenerator[str, None]:
        """Request a streaming response from the underlying AI model.

        Args:
            llm_model (str): The specific model name to query (e.g., 'gpt-4o').
            query (Any): The payload structure, usually a list of message dicts.
            start_time (datetime): The timestamp when the original request initiated.
            base_labels (dict): Pre-configured telemetry labels for metrics routing.

        Yields:
            AsyncGenerator[str, None]: Text chunks streamed directly from the provider.
        """
        pass
