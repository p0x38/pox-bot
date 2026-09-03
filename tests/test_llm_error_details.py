"""Tests for LLMManager._extract_error_details.

The method must pull out status codes, Retry-After values, and JSON
error bodies from the various exception shapes the SDK / HTTP stack
may produce, so that logs give operators an actionable picture.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

# Add src to path to allow imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from poxbot.features.ai.manager import LLMManager


class ResponseError(RuntimeError):
    """RuntimeError carrying an HTTP-style response."""

    def __init__(self, message: str, response: Any) -> None:
        super().__init__(message)
        self.response = response


class StatusCodeError(RuntimeError):
    """RuntimeError carrying an HTTP status code."""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


class DummyBot:
    """Stand-in for the bot: only the attributes the manager touches."""

    def __init__(self) -> None:
        self.metrics = None


def _make_manager() -> LLMManager:
    """Build an LLMManager without running __init__'s side effects."""
    mgr = LLMManager.__new__(LLMManager)
    mgr.bot = DummyBot()  # type: ignore[assignment]
    mgr.logger = MagicMock()
    mgr._strategy_cache = {}
    return mgr


def test_extracts_status_code_from_exception_attribute() -> None:
    """Some exceptions expose .status_code directly (e.g. HTTPError)."""
    err = StatusCodeError('boom', 503)

    mgr = _make_manager()
    details = mgr._extract_error_details(err)

    assert details['status_code'] == 503
    assert details['error_type'] == 'StatusCodeError'


def test_extracts_retry_after_from_response_headers() -> None:
    """Retry-After must be parsed from response.headers when present."""
    response = MagicMock()
    response.status_code = 429
    response.headers = {'Retry-After': '30'}
    response.json.side_effect = ValueError
    err = ResponseError('boom', response)

    mgr = _make_manager()
    details = mgr._extract_error_details(err)

    assert details['status_code'] == 429
    assert details['retry_after'] == '30'


def test_extracts_message_from_json_error_body() -> None:
    """If the response is JSON with an 'error' key, surface that message."""
    response = MagicMock()
    response.status_code = 400
    response.headers = {}
    response.json.return_value = {'error': 'bad prompt'}
    err = ResponseError('fallback message', response)

    mgr = _make_manager()
    details = mgr._extract_error_details(err)

    assert details['message'] == 'bad prompt'


def test_extracts_retry_after_from_json_body() -> None:
    """Some providers nest retry_after inside the JSON error body."""
    response = MagicMock()
    response.status_code = 429
    response.headers = {}
    response.json.return_value = {
        'error': 'rate limited',
        'retry_after': 5,
    }
    err = ResponseError('rate limited', response)

    mgr = _make_manager()
    details = mgr._extract_error_details(err)

    assert details['retry_after'] == 5


def test_falls_back_to_str_when_response_unavailable() -> None:
    """A bare exception with no HTTP metadata must not crash the parser."""
    err = ValueError('plain error')

    mgr = _make_manager()
    details = mgr._extract_error_details(err)

    assert details['status_code'] is None
    assert details['retry_after'] is None
    assert details['message'] == 'plain error'
    assert details['error_type'] == 'ValueError'


def test_unreadable_json_body_falls_back_to_string_message() -> None:
    """If the response is not valid JSON, keep the str(exception) message."""
    response = MagicMock()
    response.status_code = 500
    response.headers = {}
    response.json.side_effect = ValueError('not json')
    err = ResponseError('original message', response)

    mgr = _make_manager()
    details = mgr._extract_error_details(err)

    assert details['message'] == 'original message'
    assert details['status_code'] == 500
