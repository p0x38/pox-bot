import asyncio
import logging
from typing import Any

from poxbot.infrastructure.logger.adapters import PrefixAdapter
from poxbot.infrastructure.logger.context import (
    extension_var,
    get_extension,
    get_request_id,
    request_id_var,
    set_extension,
    set_request_id,
    start_request,
)
from poxbot.infrastructure.logger.enrich import enrich_extra
from poxbot.infrastructure.logger.filters import (
    ExcludeConsoleFilter,
    SkipEmptyMessageFilter,
)


def test_request_and_extension_context_can_be_set_and_read() -> None:
    request_token = request_id_var.set(None)
    extension_token = extension_var.set(None)
    try:
        assert get_request_id() is None
        assert get_extension() is None

        assert set_request_id("request-123") == "request-123"
        set_extension("privacy")

        assert get_request_id() == "request-123"
        assert get_extension() == "privacy"
    finally:
        request_id_var.reset(request_token)
        extension_var.reset(extension_token)


def test_start_request_generates_a_new_identifier() -> None:
    previous = request_id_var.set(None)
    try:
        first = start_request()
        second = start_request()

        assert len(first) == 32
        assert len(second) == 32
        assert first != second
        assert get_request_id() == second
    finally:
        request_id_var.reset(previous)


def test_context_variables_are_isolated_between_async_tasks() -> None:
    async def read_request_id(value: str) -> str | None:
        token = request_id_var.set(value)
        try:
            await asyncio.sleep(0)
            return get_request_id()
        finally:
            request_id_var.reset(token)

    async def run() -> None:
        results = await asyncio.gather(
            read_request_id("first"),
            read_request_id("second"),
        )

        assert results == ["first", "second"]
        assert get_request_id() is None

    asyncio.run(run())


def test_enrich_extra_copies_input_and_adds_context() -> None:
    request_token = request_id_var.set("request-123")
    extension_token = extension_var.set("chatbot")
    original = {"custom": "value"}

    try:
        enriched = enrich_extra(original)

        assert enriched == {
            "custom": "value",
            "request_id": "request-123",
            "extension": "chatbot",
        }
        assert original == {"custom": "value"}
    finally:
        request_id_var.reset(request_token)
        extension_var.reset(extension_token)


def test_log_filters_exclude_console_and_empty_messages() -> None:
    record = logging.LogRecord("poxbot", logging.INFO, __file__, 1, "hello", (), None)
    assert ExcludeConsoleFilter().filter(record) is True
    assert SkipEmptyMessageFilter().filter(record) is True

    record.no_console = True
    assert ExcludeConsoleFilter().filter(record) is False

    record.msg = "   "
    assert SkipEmptyMessageFilter().filter(record) is False


def test_prefix_adapter_merges_adapter_and_context_extras() -> None:
    request_token = request_id_var.set("request-456")
    extension_token = extension_var.set("moderation")
    logger = logging.getLogger("poxbot.test")
    adapter = PrefixAdapter(logger, {"component": "adapter"})
    kwargs: dict[str, Any] = {"extra": {"operation": "check"}}

    try:
        message, processed = adapter.process("moderation event", kwargs)

        assert message == "moderation event"
        assert processed["extra"] == {
            "operation": "check",
            "request_id": "request-456",
            "extension": "moderation",
            "component": "adapter",
        }
    finally:
        request_id_var.reset(request_token)
        extension_var.reset(extension_token)
