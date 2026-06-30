import asyncio
from collections.abc import AsyncGenerator
from enum import StrEnum
from time import perf_counter
from typing import TYPE_CHECKING

from openrouter import OpenRouter

from src.config.schema import TokenConfig
from src.logger_factory.logger import setup_logger

if TYPE_CHECKING:
    from src.core.bot import PoxBot


class LLMProviderType(StrEnum):
    OPEN_ROUTER = "openrouter"
    OLLAMA = "ollama"


class LLMManager:
    def __init__(self, bot: "PoxBot", config: TokenConfig | None = None, api_key: str | None = None):
        self.bot = bot
        self.logger = setup_logger(__name__)
        self.config = config
        self.api_key = api_key
        self.preferred = LLMProviderType.OPEN_ROUTER

    def set_preferred(self, provider: LLMProviderType):
        self.preferred = provider
    
    async def _record_metric(self, name: str, description: str, m_type: str, value_or_amount: float, labels: dict):
        if self.bot and getattr(self.bot, "metrics", None):
            if m_type == "counter":
                self.bot.metrics.increment_counter(name=name, description=description, amount=int(value_or_amount), labels=labels)
            elif m_type == "histogram":
                self.bot.metrics.record_histogram(name=name, description=description, value=value_or_amount, labels=labels)

    async def generate_response(self, input_data: dict) -> AsyncGenerator[str, None]:
        if not input_data:
            raise RuntimeError("Input data must not be empty")

        provider_type = input_data.get("provider")
        llm_model = input_data.get("model")
        query = input_data.get("query")

        if not provider_type or not llm_model or not query:
            raise ValueError("Provider, model, and query must not be empty")

        if not isinstance(provider_type, str) or not isinstance(llm_model, str):
            raise TypeError("Provider type and LLM model must be strings")
        
        base_labels = {"provider": str(provider_type), "model": str(llm_model)}
        start_time = perf_counter()

        match provider_type:
            case LLMProviderType.OPEN_ROUTER.value:
                if not isinstance(query, list):
                    raise TypeError("Query must be a list")

                current_api_key = self.api_key or getattr(self.config, "openrouter_api_key", None)

                try:
                    async with OpenRouter(api_key=current_api_key) as client:
                        self.logger.info("Requesting response to OpenRouter...")
                        thinking = False
                        generating = False
                        ttft_recorded = False

                        response = await client.chat.send_async(
                            model=llm_model,
                            messages=query,
                            stream=True
                        )

                        async for chunk in response:
                            if not thinking:
                                thinking = True
                                self.logger.info("LLM is thinking...")

                            if chunk.choices and chunk.choices[0].delta.content:
                                if not ttft_recorded:
                                    ttft_duration = perf_counter() - start_time
                                    await self._record_metric(
                                        name="bot_llm_ttft_seconds",
                                        m_type="histogram",
                                        value_or_amount=ttft_duration,
                                        labels=base_labels,
                                        description="Time to first token (TTFT) for LLM responses in seconds"
                                    )
                                    ttft_recorded = True
                                if not generating:
                                    generating = True
                                    self.logger.info("LLM is generating response...")

                                yield chunk.choices[0].delta.content
                            
                        total_duration = perf_counter() - start_time
                        await self._record_metric(
                            name="bot_llm_generation_duration_seconds",
                            m_type="histogram",
                            value_or_amount=total_duration,
                            labels=base_labels,
                            description="The total execution duration of LLM generations in seconds"
                        )
                        await self._record_metric(
                            name="bot_llm_requests_total",
                            m_type="counter",
                            value_or_amount=1,
                            labels={**base_labels, "status": "success", "error_type": "none"},
                            description="Total count of requests sent to the LLM providers"
                        )
                except Exception as e:
                    msg = str(e)
                    error_type = "generic"
                    
                    if "401" in msg or "unauthorized" in msg.lower() or "invalid api key" in msg.lower():
                        error_type = "auth"
                        self.logger.error("Authentication error when contacting OpenRouter: %s", msg)
                        parsed_exception = RuntimeError("Authentication failed when contacting the LLM provider. Check API key.")
                    elif "timeout" in msg.lower() or isinstance(e, asyncio.TimeoutError):
                        error_type = "timeout"
                        self.logger.warning("Timeout while generating response: %s", msg)
                        parsed_exception = RuntimeError("The LLM request timed out. Try again later.")
                    else:
                        self.logger.exception(f"Failed to generate response: {e}")
                        parsed_exception = RuntimeError(f"Failed to generate response: {e}")

                    await self._record_metric(
                        name="bot_llm_requests_total",
                        m_type="counter",
                        value_or_amount=1,
                        labels={**base_labels, "status": "error", "error_type": error_type},
                        description="Total count of requests sent to the LLM providers"
                    )
                    raise parsed_exception from e
            case _:
                raise ValueError(f"Unknown provider type: {provider_type}")
