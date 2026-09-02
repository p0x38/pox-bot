import asyncio
from contextlib import asynccontextmanager
from enum import StrEnum
from typing import TYPE_CHECKING, Any

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
    """No-op span used when telemetry is unavailable."""

    def set_attribute(self, *args: Any, **kwargs: Any) -> None:
        pass

    def add_event(self, *args: Any, **kwargs: Any) -> None:
        pass

    def record_exception(self, *args: Any, **kwargs: Any) -> None:
        pass

    def set_status(self, *args: Any, **kwargs: Any) -> None:
        pass


class LLMProviderType(StrEnum):
    """Supported LLM providers."""

    OPEN_ROUTER = 'openrouter'
    OLLAMA = 'ollama'
    GEMINI = 'gemini'
    OPENAI = 'openai'


class LLMManager:
    """Manages LLM providers using the strategy pattern."""

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

    def set_preferred(self, provider: LLMProviderType) -> None:
        """Set the preferred LLM provider."""
        self.preferred = provider

    async def _record_metric(
        self,
        name: str,
        description: str,
        m_type: str,
        value_or_amount: float,
        labels: dict[str, str],
    ) -> None:
        """Record a metric if metrics are available."""
        metrics: Metrics | None = getattr(self.bot, 'metrics', None)

        if not metrics:
            return

        if m_type == 'counter':
            metrics.increment_counter(
                name=name,
                description=description,
                amount=int(value_or_amount),
                labels=labels,
            )
        elif m_type == 'histogram':
            metrics.record_histogram(
                name=name,
                description=description,
                value=value_or_amount,
                labels=labels,
            )

    def _get_provider_strategy(
        self,
        provider_type: str,
    ) -> BaseLLMProvider:
        """Get or create the strategy for a provider."""
        if provider_type in self._strategy_cache:
            return self._strategy_cache[provider_type]

        match provider_type:
            case LLMProviderType.OPEN_ROUTER.value:
                current_api_key = self.api_key or getattr(
                    self.config,
                    'openrouter_api_key',
                    None,
                )

                strategy = OpenRouterStreamer(
                    self,
                    current_api_key,
                )

                self._strategy_cache[provider_type] = strategy
                return strategy

            case _:
                try:
                    LLMProviderType(provider_type)
                except ValueError:
                    raise UnknownProvider(provider_type) from None

                raise NotImplementedProvider(provider_type)

    def _extract_error_details(self, exception: Exception) -> dict[str, Any]:
        """
        Extract useful information from an API/provider exception.

        Handles common HTTP-style exceptions as well as exceptions
        containing OpenRouter-style JSON error information.
        """
        details: dict[str, Any] = {
            'error_type': type(exception).__name__,
            'message': str(exception),
            'status_code': None,
            'retry_after': None,
            'error_code': None,
            'full_exception': str(exception),
        }

        # ---------------------------------------------------------
        # HTTP status code
        # ---------------------------------------------------------

        status_code = getattr(exception, 'status_code', None)

        if status_code is None:
            response = getattr(exception, 'response', None)

            if response is not None:
                status_code = getattr(response, 'status_code', None)

        details['status_code'] = status_code

        # ---------------------------------------------------------
        # Headers
        # ---------------------------------------------------------

        headers = getattr(exception, 'headers', None)

        if headers is None:
            response = getattr(exception, 'response', None)
            headers = getattr(response, 'headers', None)

        if headers:
            details['retry_after'] = (
                headers.get('Retry-After')
                or headers.get('retry-after')
            )

        # ---------------------------------------------------------
        # JSON response body
        # ---------------------------------------------------------

        response = getattr(exception, 'response', None)

        if response is not None:
            try:
                json_data = response.json()

                if isinstance(json_data, dict):
                    error_data = json_data.get('error')

                    if isinstance(error_data, dict):
                        details['message'] = (
                            error_data.get('message')
                            or details['message']
                        )

                        details['error_code'] = (
                            error_data.get('code')
                            or error_data.get('type')
                        )

                        if error_data.get('metadata'):
                            metadata = error_data['metadata']

                            if isinstance(metadata, dict):
                                details['retry_after'] = (
                                    metadata.get('retry_after')
                                    or details['retry_after']
                                )

                    elif error_data:
                        details['message'] = str(error_data)

                    details['retry_after'] = (
                        json_data.get('retry_after')
                        or details['retry_after']
                    )

            except Exception:
                # Not all response objects support JSON decoding.
                # TODO: log exception
                pass

        return details

    @staticmethod
    def _classify_error(
        exception: Exception,
        details: dict[str, Any],
    ) -> tuple[str, str]:
        """
        Classify an exception into a stable error category.

        Returns:
            (error_type, user_message)
        """
        message = str(details.get('message') or exception)
        message_lower = message.lower()

        exception_name = type(exception).__name__.lower()

        status_code = details.get('status_code')

        # ---------------------------------------------------------
        # Quota / rate limiting
        # ---------------------------------------------------------

        if (
            status_code == 429
            or 'toomanyrequests' in exception_name
            or 'rate limit' in message_lower
            or 'rate_limit' in message_lower
            or 'too many requests' in message_lower
            or 'quota exceeded' in message_lower
            or 'quota_exceeded' in message_lower
            or 'insufficient quota' in message_lower
            or 'credits exhausted' in message_lower
            or 'credit exhausted' in message_lower
            or 'no credits' in message_lower
        ):
            retry_after = details.get('retry_after')

            if retry_after is not None:
                return (
                    'ratelimit',
                    f'LLM rate limit reached. Try again in {retry_after} seconds.',
                )

            return (
                'ratelimit',
                'LLM rate limit or quota reached. Please try again later.',
            )

        # ---------------------------------------------------------
        # Authentication
        # ---------------------------------------------------------

        if (
            status_code in {401, 403}
            or 'unauthorized' in message_lower
            or 'invalid api key' in message_lower
            or 'invalid_api_key' in message_lower
            or 'authentication' in message_lower
            or 'api key' in message_lower
        ):
            return (
                'auth',
                'Authentication failed when contacting the LLM provider. '
                'Check the API key.',
            )

        # ---------------------------------------------------------
        # Timeout
        # ---------------------------------------------------------

        if (
            isinstance(exception, asyncio.TimeoutError)
            or 'timeout' in message_lower
            or 'timed out' in message_lower
        ):
            return (
                'timeout',
                'The LLM request timed out. Please try again later.',
            )

        # ---------------------------------------------------------
        # Provider/server errors
        # ---------------------------------------------------------

        if (
            status_code is not None
            and status_code >= 500
        ) or (
            'bad gateway' in message_lower
            or 'service unavailable' in message_lower
            or 'gateway timeout' in message_lower
            or 'provider returned error' in message_lower
            or 'internal server error' in message_lower
        ):
            return (
                'provider_error',
                'The AI provider is currently unavailable or overloaded. '
                'Please try again later.',
            )

        # ---------------------------------------------------------
        # Generic failure
        # ---------------------------------------------------------

        return (
            'generic',
            f'Failed to generate response: {exception}',
        )

    @asynccontextmanager
    async def span(self, name: str, **attrs: Any):
        """Create a telemetry span when metrics/telemetry are available."""
        metrics: Metrics | None = getattr(self.bot, 'metrics', None)

        if not metrics:
            yield NullSpan()
            return

        async with metrics.span_async(name, **attrs) as span:
            yield span

    @asynccontextmanager
    async def generate_response(self, input_data: dict):
        """Generate a streaming response from the selected provider."""
        if not input_data:
            raise EmptyInput()

        provider_type = input_data.get('provider')
        llm_model = input_data.get('model')
        query = input_data.get('query')

        if not provider_type or not llm_model or not query:
            raise MissingInput()

        if not isinstance(provider_type, str):
            raise InvalidData()

        if not isinstance(llm_model, str):
            raise InvalidData()

        async with self.span(
            'llm.request',
            provider=provider_type,
            model=llm_model,
        ) as span:
            span.set_attribute('provider', provider_type)
            span.set_attribute('model', llm_model)

            strategy = self._get_provider_strategy(provider_type)

            base_labels = {
                'provider': provider_type,
                'model': llm_model,
            }

            ctx = LLMRequestContext()

            try:
                # -------------------------------------------------
                # Start provider stream
                # -------------------------------------------------

                stream = strategy.stream_response(
                    llm_model,
                    query,
                    ctx,
                    base_labels,
                )

                # -------------------------------------------------
                # Stream response
                # -------------------------------------------------

                async for chunk in stream:
                    yield chunk

                # -------------------------------------------------
                # Successful request
                # -------------------------------------------------

                span.set_attribute('status', 'success')
                span.set_attribute(
                    'duration_seconds',
                    ctx.elapsed_seconds,
                )

                await self._record_metric(
                    name='bot_llm_generation_duration_seconds',
                    m_type='histogram',
                    value_or_amount=ctx.elapsed_seconds,
                    labels=base_labels,
                    description=(
                        'Total execution duration of LLM generations in seconds'
                    ),
                )

                await self._record_metric(
                    name='bot_llm_requests_total',
                    m_type='counter',
                    value_or_amount=1,
                    labels={
                        **base_labels,
                        'status': 'success',
                        'error_type': 'none',
                    },
                    description=(
                        'Total count of requests sent to LLM providers'
                    ),
                )

            except Exception as exception:
                # -------------------------------------------------
                # Extract + classify error
                # -------------------------------------------------

                details = self._extract_error_details(exception)

                error_type, user_message = self._classify_error(
                    exception,
                    details,
                )

                status_code = details.get('status_code')
                retry_after = details.get('retry_after')

                # -------------------------------------------------
                # Telemetry
                # -------------------------------------------------

                span.record_exception(exception)
                span.set_attribute('status', 'error')
                span.set_attribute('error_type', error_type)

                if status_code is not None:
                    span.set_attribute(
                        'http.status_code',
                        status_code,
                    )

                if retry_after is not None:
                    span.set_attribute(
                        'retry_after',
                        str(retry_after),
                    )

                span.set_status(trace.StatusCode.ERROR)

                # -------------------------------------------------
                # Logging
                # -------------------------------------------------

                self.logger.error(
                    'LLM request failed | '
                    'type=%s | status=%s | retry_after=%s | message=%s',
                    error_type,
                    status_code or 'N/A',
                    retry_after or 'N/A',
                    details.get('message', str(exception)),
                )

                # Rate limits are expected provider-side failures,
                # so warning is more appropriate than exception-level
                # logging.
                if error_type == 'ratelimit':
                    self.logger.warning(
                        'LLM rate limit/quota reached | '
                        'provider=%s | model=%s | retry_after=%s',
                        provider_type,
                        llm_model,
                        retry_after or 'unknown',
                    )

                elif error_type == 'auth':
                    self.logger.error(
                        'LLM authentication failed | '
                        'provider=%s | model=%s',
                        provider_type,
                        llm_model,
                    )

                elif error_type == 'timeout':
                    self.logger.warning(
                        'LLM request timed out | '
                        'provider=%s | model=%s',
                        provider_type,
                        llm_model,
                    )

                else:
                    self.logger.exception(
                        'Unexpected LLM provider failure',
                    )

                # -------------------------------------------------
                # Error metric
                # -------------------------------------------------

                await self._record_metric(
                    name='bot_llm_requests_total',
                    m_type='counter',
                    value_or_amount=1,
                    labels={
                        **base_labels,
                        'status': 'error',
                        'error_type': error_type,
                    },
                    description=(
                        'Total count of requests sent to LLM providers'
                    ),
                )

                # -------------------------------------------------
                # Raise stable application-level exception
                # -------------------------------------------------

                raise RuntimeError(user_message) from exception
