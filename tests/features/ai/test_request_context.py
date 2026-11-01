from dataclasses import FrozenInstanceError
from datetime import timedelta
from time import sleep

import pytest

from poxbot.features.ai.request_context import LLMRequestContext


def test_request_context_uses_utc_wall_clock_snapshot() -> None:
    context = LLMRequestContext()

    assert context.start_time.utcoffset() == timedelta(0)
    assert context.start_tick > 0


def test_request_context_elapsed_time_is_monotonic() -> None:
    context = LLMRequestContext()

    sleep(0.001)

    assert context.elapsed_seconds > 0


def test_request_context_is_immutable() -> None:
    context = LLMRequestContext()

    with pytest.raises(FrozenInstanceError):
        context.start_tick = 0.0  # type: ignore[misc]
