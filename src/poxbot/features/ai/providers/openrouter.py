import asyncio
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any

from openrouter import OpenRouter

from ..request_context import LLMRequestContext

if TYPE_CHECKING:
    from ....services.ai import LLMManager

from ....shared.abc.base_provider import BaseLLMProvider
from ....shared.exceptions.ai_error import InvalidQueryData


class OpenRouterStreamer(BaseLLMProvider):
    """OpenRouter implementation of BaseLLMProvider.

    Handles:
    - Streaming responses
    - TTFT metrics
    - Temporary rate-limit retries
    - Retry-After handling
    - Permanent quota/credit failures

    Quota exhaustion is deliberately NOT retried because retrying an
    exhausted quota cannot make the request succeed.
    """

    MAX_RETRIES = 3
    INITIAL_BACKOFF = 2.0
    MAX_BACKOFF = 30.0
    BACKOFF_MULTIPLIER = 2.0

    def __init__(
        self,
        manager: 'LLMManager',
        api_key: str | None,
    ):
        """Initialize the OpenRouter client."""
        self.mgr = manager
        self.api_key = api_key

        self.client = OpenRouter(
            api_key=self.api_key,
        )

    async def stream_response(
        self,
        llm_model: str,
        query: Any,
        ctx: LLMRequestContext,
        base_labels: dict[str, str],
    ) -> AsyncGenerator[str, None]:
        """Stream a response from OpenRouter.

        Temporary rate limits are retried with exponential backoff.

        Permanent quota/credit exhaustion is raised immediately.

        Args:
            llm_model: OpenRouter model ID.
            query: OpenAI-compatible messages list.
            ctx: Request timing context.
            base_labels: Metric labels.

        Yields:
            Response text chunks.

        Raises:
            InvalidQueryData: If query is not a message list.
            Exception: If the request fails.
        """
        if not isinstance(query, list):
            raise InvalidQueryData()

        retry_count = 0
        backoff_time = self.INITIAL_BACKOFF

        while True:
            try:
                self.mgr.logger.info(
                    'Requesting response from OpenRouter at %s (attempt %d/%d)',
                    ctx.start_time.isoformat(),
                    retry_count + 1,
                    self.MAX_RETRIES + 1,
                )

                response = await self.client.chat.send_async(
                    model=llm_model,
                    messages=query,
                    stream=True,
                )

                thinking_logged = False
                generating_logged = False
                ttft_recorded = False

                async for chunk in response:
                    if not thinking_logged:
                        thinking_logged = True
                        self.mgr.logger.info('LLM is thinking...')

                    choice = chunk.choices[0] if chunk.choices else None

                    content = getattr(choice.delta, 'content', None) if choice else None

                    if not content:
                        continue

                    # ---------------------------------------------
                    # TTFT
                    # ---------------------------------------------

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

                    # ---------------------------------------------
                    # Generation logging
                    # ---------------------------------------------

                    if not generating_logged:
                        generating_logged = True
                        self.mgr.logger.info('LLM is generating response...')

                    yield content

                # -------------------------------------------------
                # Successful stream
                # -------------------------------------------------

                return

            except Exception as exception:
                error_msg = str(exception)

                classification = self._classify_error(
                    exception,
                )

                # -------------------------------------------------
                # Permanent quota failure
                # -------------------------------------------------

                if classification == 'quota':
                    self.mgr.logger.error(
                        'OpenRouter quota/credits exhausted. '
                        'Request will NOT be retried. '
                        'model=%s | error=%s',
                        llm_model,
                        error_msg,
                    )

                    raise

                # -------------------------------------------------
                # Authentication failure
                # -------------------------------------------------

                if classification == 'auth':
                    self.mgr.logger.error(
                        'OpenRouter authentication failed. '
                        'Request will NOT be retried. '
                        'model=%s | error=%s',
                        llm_model,
                        error_msg,
                    )

                    raise

                # -------------------------------------------------
                # Non-rate-limit error
                # -------------------------------------------------

                if classification != 'ratelimit':
                    self.mgr.logger.error(
                        'OpenRouter request failed. model=%s | error=%s',
                        llm_model,
                        error_msg,
                    )

                    raise

                # -------------------------------------------------
                # Rate limit
                # -------------------------------------------------

                if retry_count >= self.MAX_RETRIES:
                    self.mgr.logger.error(
                        'OpenRouter rate-limit retries exhausted '
                        'after %d attempts. Last error: %s',
                        retry_count + 1,
                        error_msg,
                    )

                    raise

                retry_after = self._extract_retry_after(
                    exception,
                )

                if retry_after is not None:
                    wait_time = min(
                        float(retry_after),
                        self.MAX_BACKOFF,
                    )
                else:
                    wait_time = backoff_time

                retry_count += 1

                self.mgr.logger.warning(
                    'OpenRouter rate limit hit. '
                    'Retrying in %.1f seconds '
                    '(attempt %d/%d) | error=%s',
                    wait_time,
                    retry_count + 1,
                    self.MAX_RETRIES + 1,
                    error_msg,
                )

                await asyncio.sleep(wait_time)

                # Always continue our own bounded exponential
                # schedule rather than exponentially multiplying
                # Retry-After values.
                backoff_time = min(
                    backoff_time * self.BACKOFF_MULTIPLIER,
                    self.MAX_BACKOFF,
                )

    @staticmethod
    def _classify_error(exception: Exception) -> str:
        """Classify an OpenRouter exception.

        Returns:
            One of:
            - ``quota``
            - ``ratelimit``
            - ``auth``
            - ``other``
        """
        message = str(exception).lower()
        exception_name = type(exception).__name__.lower()

        status_code = getattr(
            exception,
            'status_code',
            None,
        )

        if status_code is None:
            response = getattr(
                exception,
                'response',
                None,
            )

            if response is not None:
                status_code = getattr(
                    response,
                    'status_code',
                    None,
                )

        # ---------------------------------------------------------
        # Quota / credits
        #
        # IMPORTANT:
        # These must be checked BEFORE generic 429 detection.
        # ---------------------------------------------------------

        quota_indicators = (
            'quota exceeded',
            'quota_exceeded',
            'insufficient quota',
            'insufficient credits',
            'credits exhausted',
            'credit exhausted',
            'no credits',
            'out of credits',
            'exceeded your current quota',
            'exceeded quota',
        )

        if any(indicator in message for indicator in quota_indicators):
            return 'quota'

        # Some providers encode quota information in the
        # exception type itself.
        if 'quota' in exception_name or 'insufficientfunds' in exception_name:
            return 'quota'

        # ---------------------------------------------------------
        # Authentication
        # ---------------------------------------------------------

        if status_code in {401, 403}:
            return 'auth'

        auth_indicators = (
            'unauthorized',
            'invalid api key',
            'invalid_api_key',
            'authentication failed',
            'authentication error',
        )

        if any(indicator in message for indicator in auth_indicators):
            return 'auth'

        # ---------------------------------------------------------
        # Temporary rate limit
        # ---------------------------------------------------------

        if status_code == 429:
            return 'ratelimit'

        rate_limit_indicators = (
            'too many requests',
            'rate limit',
            'rate_limit',
            'ratelimit',
            'temporarily rate limited',
        )

        if any(indicator in message for indicator in rate_limit_indicators):
            return 'ratelimit'

        if 'toomanyrequests' in exception_name:
            return 'ratelimit'

        return 'other'

    @staticmethod
    def _extract_retry_after(
        exception: Exception,
    ) -> float | None:
        """Extract Retry-After from an exception.

        Supports response headers and direct exception headers.

        Returns:
            Retry delay in seconds, or None.
        """

        def parse(value: Any) -> float | None:
            if value is None:
                return None

            try:
                parsed = float(value)

                if parsed < 0:
                    return None

                return parsed

            except (TypeError, ValueError):
                return None

        # ---------------------------------------------------------
        # Exception headers
        # ---------------------------------------------------------

        headers = getattr(
            exception,
            'headers',
            None,
        )

        if headers:
            retry_after = headers.get('Retry-After') or headers.get('retry-after')

            parsed = parse(retry_after)

            if parsed is not None:
                return parsed

        # ---------------------------------------------------------
        # Response headers
        # ---------------------------------------------------------

        response = getattr(
            exception,
            'response',
            None,
        )

        if response is not None:
            response_headers = getattr(
                response,
                'headers',
                None,
            )

            if response_headers:
                retry_after = response_headers.get(
                    'Retry-After',
                ) or response_headers.get('retry-after')

                parsed = parse(retry_after)

                if parsed is not None:
                    return parsed

        return None
