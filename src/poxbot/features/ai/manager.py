import asyncio
from contextlib import asynccontextmanager
from enum import StrEnum
from typing import TYPE_CHECKING

from opentelemetry import trace

from ...config.schema import TokenConfig
from ...infrastructure.logger import get_logger
from ...shared.abc.base_provider import BaseLLMProvider
from ...shared.exceptions.ai_error import (
    EmptyInput,
    InvalidData,
    MissingInput,
    NotImplementedProvider,
    UnknownProvider,
)
from ...shared.utils.metrics import Metrics
from .providers.openrouter import OpenRouterStreamer
from .request_context import LLMRequestContext

if TYPE_CHECKING:
    from ...application.bot import PoxBot


class NullSpan:
    def set_attribute(self, *args, **kwargs):
        pass

    def add_event(self, *args, **kwargs):
        pass

    def record_exception(self, *args, **kwargs):
        pass

    def set_status(self, *args, **kwargs):
        pass


class LLMProviderType(StrEnum):
    """String enum of AI Provider."""

    OPEN_ROUTER = 'openrouter'
    OLLAMA = 'ollama'
    GEMINI = 'gemini'
    OPENAI = 'openai'


class LLMManager:
    """Manages AI providers using the strategy pattern."""

    def __init__(
        self,
        bot: 'PoxBot',
        config: TokenConfig | None = None,
        api_key: str | None = None,
    ):
        self.bot = bot
        self.logger = get_logger(__name__, prefix='AIProviderManager')
        self.config = config
        self.api_key = api_key
        self.preferred = LLMProviderType.OPEN_ROUTER

        self._strategy_cache: dict[str, BaseLLMProvider] = {}

    def set_preferred(self, provider: LLMProviderType):
        """Set preferred provider to the supplied type."""
        self.preferred = provider

    async def _record_metric(
        self,
        name: str,
        description: str,
        m_type: str,
        value_or_amount: float,
        labels: dict,
    ):
        if self.bot and self.bot.metrics:
            if m_type == 'counter':
                self.bot.metrics.increment_counter(
                    name=name,
                    description=description,
                    amount=int(value_or_amount),
                    labels=labels,
                )
            elif m_type == 'histogram':
                self.bot.metrics.record_histogram(
                    name=name,
                    description=description,
                    value=value_or_amount,
                    labels=labels,
                )

    def _get_provider_strategy(self, provider_type: str) -> BaseLLMProvider:
        if provider_type in self._strategy_cache:
            return self._strategy_cache[provider_type]

        match provider_type:
            case LLMProviderType.OPEN_ROUTER.value:
                current_api_key = self.api_key or getattr(
                    self.config,
                    'openrouter_api_key',
                    None,
                )
                strategy = OpenRouterStreamer(self, current_api_key)
                self._strategy_cache[provider_type] = strategy
                return strategy
            case _:
                if hasattr(LLMProviderType, str(provider_type).upper()):
                    raise NotImplementedProvider(provider_type)
                raise UnknownProvider(provider_type)

    @asynccontextmanager
    async def span(self, name: str, **attrs):
        metrics: Metrics | None = getattr(self.bot, 'metrics', None)
        if not metrics:
            yield NullSpan()
            return

        async with metrics.span_async(name, **attrs) as span:
            yield span

    @asynccontextmanager
    async def generate_response(self, input_data: dict):
        if not input_data:
            raise EmptyInput()

        provider_type = input_data.get('provider')
        llm_model = input_data.get('model')
        query = input_data.get('query')

        if not provider_type or not llm_model or not query:
            raise MissingInput()

        if not isinstance(provider_type, str) or not isinstance(llm_model, str):
            raise InvalidData()

        async with self.span(
            'llm.request',
            provider=str(provider_type),
            model=str(llm_model),
        ) as span:
            span.set_attribute('provider', provider_type)
            span.set_attribute('model', llm_model)

            strategy = self._get_provider_strategy(provider_type)

            base_labels = {'provider': str(provider_type), 'model': str(llm_model)}

            ctx = LLMRequestContext()

            try:
                async with self.span(
                    'llm.request',
                    provider=str(provider_type),
                    model=str(llm_model),
                ):
                    stream = strategy.stream_response(
                        llm_model,
                        query,
                        ctx,
                        base_labels,
                    )

                async for chunk in stream:
                    yield chunk

                await self._record_metric(
                    name='bot_llm_generation_duration_seconds',
                    m_type='histogram',
                    value_or_amount=ctx.elapsed_seconds,
                    labels=base_labels,
                    description=(
                        'The total execution duration of LLM generations in seconds'
                    ),
                )
                await self._record_metric(
                    name='bot_llm_requests_total',
                    m_type='counter',
                    value_or_amount=1,
                    labels={**base_labels, 'status': 'success', 'error_type': 'none'},
                    description='Total count of requests sent to the LLM providers',
                )

            except Exception as e:
                msg = str(e)
                error_type = 'generic'

                span.record_exception(e)
                span.set_attribute('error_type', error_type)
                span.set_status(trace.StatusCode.ERROR)
                if (
                    'TooManyRequests' in type(e).__name__
                    or '429' in msg
                    or 'too many requests' in msg.lower()
                ):
                    error_type = 'ratelimit'
                    self.logger.warning('Rate limit hit from provider: %s', msg)
                    parsed_exception = RuntimeError(
                        'Rate limit exceeded. Please wait a moment before trying again.',
                    )
                elif (
                    'provider returned error' in msg.lower()
                    or 'bad gateway' in msg.lower()
                ):
                    error_type = 'provider_error'
                    self.logger.exception(
                        'The underlying provider crashed or timed out: %s',
                        msg,
                    )
                    parsed_exception = RuntimeError(
                        'The AI provider is currently overloaded or down. Try again later.',
                    )
                elif (
                    '401' in msg
                    or 'unauthorized' in msg.lower()
                    or 'invalid api key' in msg.lower()
                    or 'authentication' in msg.lower()
                ):
                    error_type = 'auth'
                    self.logger.exception(
                        'Authentication error when contacting API: %s',
                        msg,
                    )
                    parsed_exception = RuntimeError(
                        'Authentication failed when contacting the LLM provider.'
                        'Check API key.',
                    )
                elif 'timeout' in msg.lower() or isinstance(e, asyncio.TimeoutError):
                    error_type = 'timeout'
                    self.logger.warning('Timeout while generating response: %s', msg)
                    parsed_exception = RuntimeError(
                        'The LLM request timed out. Try again later.',
                    )
                else:
                    self.logger.exception('Failed to generate response')
                    parsed_exception = RuntimeError(f'Failed to generate response: {e}')

                await self._record_metric(
                    name='bot_llm_requests_total',
                    m_type='counter',
                    value_or_amount=1,
                    labels={**base_labels, 'status': 'error', 'error_type': error_type},
                    description='Total count of requests sent to the LLM providers',
                )
                raise parsed_exception from e
