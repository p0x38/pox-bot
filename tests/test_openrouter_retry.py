"""Tests for OpenRouter retry mechanism and error handling.

These tests verify the rate-limit retry behavior, exponential backoff,
and the helper used to extract Retry-After headers from exceptions.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from poxbot.features.ai.manager import LLMManager

# Add src to path to allow imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from poxbot.features.ai.providers.openrouter import OpenRouterStreamer
from poxbot.features.ai.request_context import LLMRequestContext
from poxbot.shared.exceptions.ai_error import InvalidQueryData


class FakeResponse:
    """Fake HTTP response used to simulate status codes and headers."""

    def __init__(
        self,
        status_code: int = 429,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.headers = headers or {}


class FakeException(Exception):  # ruff: ignore[error-suffix-on-exception-name]
    """Fake exception that mimics OpenRouter's API exceptions."""

    def __init__(
        self,
        message: str,
        response: FakeResponse | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.response = response
        self.headers = headers or {}


class RateLimitError(FakeException):
    """Mimics openrouter.RateLimitError for testing retry behavior."""


class DummyManager:
    """Minimal stand-in for LLMManager used by OpenRouterStreamer."""

    def __init__(self) -> None:
        self.logger = MagicMock()
        self.metric_calls: list[dict[str, Any]] = []

    async def _record_metric(
        self,
        name: str,
        description: str,
        m_type: str,
        value_or_amount: float,
        labels: dict,
    ) -> None:
        self.metric_calls.append(
            {
                'name': name,
                'type': m_type,
                'value': value_or_amount,
                'labels': labels,
            },
        )


def _make_streamer(
    manager: DummyManager | None = None,
    api_key: str = 'test-key',
) -> OpenRouterStreamer:
    """Build an OpenRouterStreamer without triggering the real client."""
    manager = manager or DummyManager()
    streamer = OpenRouterStreamer.__new__(OpenRouterStreamer)
    streamer.mgr = cast(LLMManager, manager)
    streamer.api_key = api_key
    streamer.client = MagicMock()
    return streamer


def _make_rate_limit_error(
    retry_after: str | None = None,
    status_code: int = 429,
) -> RateLimitError:
    """Build a fake rate-limit exception that looks like the real one."""
    headers: dict[str, str] = {}
    if retry_after is not None:
        headers['Retry-After'] = retry_after
    err = RateLimitError('429 Too Many Requests')
    err.response = FakeResponse(status_code=status_code, headers=headers)
    err.headers = headers
    return err


class _FakeChunk:
    """Fake streaming chunk mimicking the openrouter SDK shape."""

    def __init__(self, content: str | None) -> None:
        delta = MagicMock()
        delta.content = content
        choice = MagicMock()
        choice.delta = delta
        self.choices = [choice]


@pytest.mark.asyncio
async def test_invalid_query_raises_immediately():
    """stream_response must reject non-list queries without calling the API."""
    streamer = _make_streamer()

    with pytest.raises(InvalidQueryData):
        async for _ in streamer.stream_response(
            llm_model='gpt-4o',
            query='not a list',  # type: ignore[arg-type]
            ctx=LLMRequestContext(),
            base_labels={},
        ):
            pass


@pytest.mark.asyncio
async def test_successful_response_does_not_retry():
    """A successful response on the first try should not trigger any retry."""
    manager = DummyManager()
    streamer = _make_streamer(manager=manager)

    chunks = [_FakeChunk('Hello'), _FakeChunk(' world')]
    streamer.client.chat.send_async = AsyncMock(return_value=_async_iter(chunks))

    sleep_calls: list[float] = []

    async def mock_sleep(delay: float):  # ruff: ignore[unused-async]
        sleep_calls.append(delay)
    
    with patch('poxbot.features.ai.providers.openrouter.asyncio.sleep', new=mock_sleep):
        result: list[str] = [piece async for piece in streamer.stream_response(
            llm_model='gpt-4o',
            query=[],
            ctx=LLMRequestContext(),
            base_labels={'provider': 'openrouter', 'model': 'gpt-4o'},
        )]

    assert result == ['Hello', ' world']
    assert streamer.client.chat.send_async.call_count == 1
    assert sleep_calls == []
    # TTFT metric must be recorded exactly once on success.
    assert any(c['name'] == 'bot_ai_ttft_seconds' for c in manager.metric_calls)


@pytest.mark.asyncio
async def test_rate_limit_triggers_retry_then_succeeds():
    """A 429 on the first call should be retried and eventually succeed."""
    manager = DummyManager()
    streamer = _make_streamer(manager=manager)

    rate_err = _make_rate_limit_error(retry_after='1')

    success_chunks = [_FakeChunk('ok')]
    streamer.client.chat.send_async = AsyncMock(
        side_effect=[rate_err, _async_iter(success_chunks)],
    )

    sleep_mock = AsyncMock()
    with patch('poxbot.features.ai.providers.openrouter.asyncio.sleep', new=sleep_mock):
        result: list[str] = [piece async for piece in streamer.stream_response(
            llm_model='gpt-4o',
            query=[],
            ctx=LLMRequestContext(),
            base_labels={'provider': 'openrouter', 'model': 'gpt-4o'},
        )]

    assert result == ['ok']
    assert streamer.client.chat.send_async.call_count == 2
    # We must have slept once with the value from Retry-After.
    sleep_mock.assert_awaited_once()
    args, _ = sleep_mock.call_args
    assert args[0] == 1


@pytest.mark.asyncio
async def test_rate_limit_exhausts_retries_and_raises():
    """When retries are exhausted, the last error must be re-raised."""
    manager = DummyManager()
    streamer = _make_streamer(manager=manager)

    rate_err = _make_rate_limit_error(retry_after='1')
    streamer.client.chat.send_async = AsyncMock(side_effect=rate_err)

    with patch(
        'src.poxbot.features.ai.providers.openrouter.asyncio.sleep',
        new=AsyncMock(),
    ), pytest.raises(RateLimitError):
        async for _ in streamer.stream_response(
            llm_model='gpt-4o',
            query=[],
            ctx=LLMRequestContext(),
            base_labels={'provider': 'openrouter', 'model': 'gpt-4o'},
        ):
            pass

    # 1 initial attempt + 3 retries = 4 calls total.
    assert streamer.client.chat.send_async.call_count == (
        OpenRouterStreamer.MAX_RETRIES + 1
    )
    manager.logger.error.assert_called()


@pytest.mark.asyncio
async def test_non_rate_limit_error_does_not_retry():
    """Generic errors (e.g. ValueError) must not trigger any retry loop."""
    manager = DummyManager()
    streamer = _make_streamer(manager=manager)

    boom = ValueError('something broke')
    streamer.client.chat.send_async = AsyncMock(side_effect=boom)

    with patch(
        'src.poxbot.features.ai.providers.openrouter.asyncio.sleep',
        new=AsyncMock(),
    ) as sleep_mock, pytest.raises(ValueError):  # ruff: ignore[pytest-raises-too-broad]
        async for _ in streamer.stream_response(
            llm_model='gpt-4o',
            query=[],
            ctx=LLMRequestContext(),
            base_labels={'provider': 'openrouter', 'model': 'gpt-4o'},
        ):
            pass

    assert streamer.client.chat.send_async.call_count == 1
    sleep_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_exponential_backoff_when_no_retry_after_header():
    """If Retry-After is missing, backoff must follow the exponential schedule."""
    manager = DummyManager()
    streamer = _make_streamer(manager=manager)

    # No Retry-After header at all.
    rate_err = RateLimitError('429')
    rate_err.response = FakeResponse(status_code=429, headers={})
    rate_err.headers = {}

    streamer.client.chat.send_async = AsyncMock(side_effect=rate_err)

    sleep_mock = AsyncMock()
    with patch(
        'src.poxbot.features.ai.providers.openrouter.asyncio.sleep',
        new=sleep_mock,
    ), pytest.raises(RateLimitError):
        async for _ in streamer.stream_response(
            llm_model='gpt-4o',
            query=[],
            ctx=LLMRequestContext(),
            base_labels={'provider': 'openrouter', 'model': 'gpt-4o'},
        ):
            pass

    delays = [c.args[0] for c in sleep_mock.call_args_list]
    # Three retries -> three sleeps with exponential growth.
    assert delays == [2, 4, 8]
    # No delay should exceed the configured cap.
    assert max(delays) <= OpenRouterStreamer.MAX_BACKOFF


@pytest.mark.parametrize(
    ('headers_attr', 'expected'),
    [
        ({'Retry-After': '15'}, 15),
        ({'retry-after': '7'}, 7),  # case-insensitive
        ({}, None),
        ({'Retry-After': 'not-a-number'}, None),
    ],
)
def test_extract_retry_after_from_response_headers(
    headers_attr: dict[str, str],
    expected: int | None,
) -> None:
    """_extract_retry_after must read response headers case-insensitively."""
    err = FakeException('boom')
    err.response = FakeResponse(headers=headers_attr)
    err.headers = {}

    streamer = _make_streamer()
    assert streamer._extract_retry_after(err) == expected


def test_extract_retry_after_from_exception_headers() -> None:
    """Fallback: read headers attached directly to the exception."""
    err = FakeException('boom')
    err.headers = {'Retry-After': '42'}

    streamer = _make_streamer()
    assert streamer._extract_retry_after(err) == 42


def test_extract_retry_after_returns_none_when_missing() -> None:
    """If no header is present anywhere, return None (fall back to backoff)."""
    err = FakeException('boom')

    streamer = _make_streamer()
    assert streamer._extract_retry_after(err) is None


async def _async_iter(items: list[Any]):  # ruff: ignore[unused-async]
    """Tiny helper to build an async iterator from a list."""
    for item in items:
        yield item
