"""Tests for the Pygent-backed OpenRouter provider adapter."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from poxbot.features.ai.manager import LLMManager
from poxbot.features.ai.providers.openrouter import OpenRouterStreamer
from poxbot.features.ai.request_context import LLMRequestContext
from poxbot.shared.exceptions.ai_error import InvalidQueryData


def make_query(*messages: tuple[str, str]) -> list[dict[str, str]]:
    """Create a message history."""
    return [
        {
            'role': role,
            'content': content,
        }
        for role, content in messages
    ]


def make_manager() -> MagicMock:
    """Create a mocked LLMManager."""
    manager = MagicMock(spec=LLMManager)

    async def record_metric(  # ruff: ignore[unused-async]
        *,
        name: str,
        description: str,
        m_type: str,
        value_or_amount: float,
        labels: dict[str, str],
    ) -> None:
        manager.metric_calls.append(
            {
                'name': name,
                'description': description,
                'type': m_type,
                'value': value_or_amount,
                'labels': labels,
            },
        )

    manager.metric_calls = []
    manager._record_metric = AsyncMock(side_effect=record_metric)

    return manager


def make_streamer() -> tuple[OpenRouterStreamer, MagicMock]:
    manager = MagicMock(spec=LLMManager)
    manager._record_metric = AsyncMock()
    manager.logger = MagicMock()

    streamer = OpenRouterStreamer(
        manager,
        api_key='test-key',
    )

    return streamer, manager


def make_provider() -> MagicMock:
    """Create a mocked Pygent provider."""
    provider = MagicMock()
    provider.aclose = AsyncMock()
    return provider


@pytest.mark.asyncio
async def test_empty_query_raises() -> None:
    """An empty query must be rejected."""
    streamer, _ = make_streamer()

    with pytest.raises(InvalidQueryData):
        async for _ in streamer.stream_response(
            llm_model='test-model',
            query=[],
            ctx=LLMRequestContext(),
            base_labels={},
        ):
            pass


@pytest.mark.asyncio
async def test_invalid_query_type_raises() -> None:
    """A non-list query must be rejected."""
    streamer, _ = make_streamer()

    with pytest.raises(InvalidQueryData):
        async for _ in streamer.stream_response(
            llm_model='test-model',
            query='hello',  # type: ignore[arg-type]
            ctx=LLMRequestContext(),
            base_labels={},
        ):
            pass


@pytest.mark.asyncio
async def test_invalid_message_raises() -> None:
    """Invalid message data must be rejected."""
    streamer, _ = make_streamer()

    with pytest.raises(InvalidQueryData):
        async for _ in streamer.stream_response(
            llm_model='test-model',
            query=[{'invalid': 'message'}],
            ctx=LLMRequestContext(),
            base_labels={},
        ):
            pass


@pytest.mark.asyncio
async def test_response_is_yielded() -> None:
    """The generated response should be yielded to the caller."""
    streamer, _ = make_streamer()

    provider = make_provider()
    agent = MagicMock()
    agent.run = AsyncMock(
        return_value=SimpleNamespace(text='hello from Pygent'),
    )

    with (
        patch(
            'poxbot.features.ai.providers.openrouter.OpenRouterProvider',
            return_value=provider,
        ),
        patch(
            'poxbot.features.ai.providers.openrouter.Agent',
            return_value=agent,
        ),
    ):
        result = [
            chunk
            async for chunk in streamer.stream_response(
                llm_model='test-model',
                query=make_query(('user', 'hello')),
                ctx=LLMRequestContext(),
                base_labels={},
            )
        ]

    assert result == ['hello from Pygent']


@pytest.mark.asyncio
async def test_empty_response_is_not_yielded() -> None:
    """An empty response should not produce a chunk."""
    streamer, _ = make_streamer()

    provider = make_provider()
    agent = MagicMock()
    agent.run = AsyncMock(
        return_value=SimpleNamespace(text=''),
    )

    with (
        patch(
            'poxbot.features.ai.providers.openrouter.OpenRouterProvider',
            return_value=provider,
        ),
        patch(
            'poxbot.features.ai.providers.openrouter.Agent',
            return_value=agent,
        ),
    ):
        result = [
            chunk
            async for chunk in streamer.stream_response(
                llm_model='test-model',
                query=make_query(('user', 'hello')),
                ctx=LLMRequestContext(),
                base_labels={},
            )
        ]

    assert result == []


@pytest.mark.asyncio
async def test_history_is_seeded() -> None:
    """Previous messages should be seeded into conversation memory."""
    streamer, _ = make_streamer()

    provider = make_provider()
    agent = MagicMock()
    agent.run = AsyncMock(
        return_value=SimpleNamespace(text='response'),
    )

    query = make_query(
        ('user', 'first message'),
        ('assistant', 'previous response'),
        ('user', 'current message'),
    )

    with (
        patch(
            'poxbot.features.ai.providers.openrouter.OpenRouterProvider',
            return_value=provider,
        ),
        patch(
            'poxbot.features.ai.providers.openrouter.ConversationMemory',
        ) as memory_cls,
        patch(
            'poxbot.features.ai.providers.openrouter.Agent',
            return_value=agent,
        ),
    ):
        [
            chunk
            async for chunk in streamer.stream_response(
                llm_model='test-model',
                query=query,
                ctx=LLMRequestContext(),
                base_labels={},
            )
        ]

    memory = memory_cls.return_value
    memory.seed.assert_called_once()

    history = memory.seed.call_args.args[0]

    assert len(history) == 2
    assert history[0].content == 'first message'
    assert history[1].content == 'previous response'


@pytest.mark.asyncio
async def test_latest_message_is_passed_to_agent() -> None:
    """Only the latest message should be passed directly to Agent.run."""
    streamer, _ = make_streamer()

    provider = make_provider()
    agent = MagicMock()
    agent.run = AsyncMock(
        return_value=SimpleNamespace(text='response'),
    )

    query = make_query(
        ('user', 'old message'),
        ('assistant', 'old response'),
        ('user', 'latest message'),
    )

    with (
        patch(
            'poxbot.features.ai.providers.openrouter.OpenRouterProvider',
            return_value=provider,
        ),
        patch(
            'poxbot.features.ai.providers.openrouter.Agent',
            return_value=agent,
        ),
    ):
        [
            chunk
            async for chunk in streamer.stream_response(
                llm_model='test-model',
                query=query,
                ctx=LLMRequestContext(),
                base_labels={},
            )
        ]

    message = agent.run.call_args.args[0]

    assert message.content == 'latest message'


@pytest.mark.asyncio
async def test_provider_configuration() -> None:
    """The Pygent OpenRouter provider should receive the expected settings."""
    streamer, _ = make_streamer()

    provider = make_provider()
    agent = MagicMock()
    agent.run = AsyncMock(
        return_value=SimpleNamespace(text='response'),
    )

    with (
        patch(
            'poxbot.features.ai.providers.openrouter.OpenRouterProvider',
            return_value=provider,
        ) as provider_cls,
        patch(
            'poxbot.features.ai.providers.openrouter.Agent',
            return_value=agent,
        ),
    ):
        [
            chunk
            async for chunk in streamer.stream_response(
                llm_model='test-model',
                query=make_query(('user', 'hello')),
                ctx=LLMRequestContext(),
                base_labels={},
            )
        ]

    provider_cls.assert_called_once_with(
        'test-model',
        api_key='test-key',
        app_name='pox-bot',
    )


@pytest.mark.asyncio
async def test_agent_configuration() -> None:
    """The Pygent Agent should receive the expected limits."""
    streamer, _ = make_streamer()

    provider = make_provider()
    agent = MagicMock()
    agent.run = AsyncMock(
        return_value=SimpleNamespace(text='response'),
    )

    with (
        patch(
            'poxbot.features.ai.providers.openrouter.OpenRouterProvider',
            return_value=provider,
        ),
        patch(
            'poxbot.features.ai.providers.openrouter.ConversationMemory',
        ) as memory_cls,
        patch(
            'poxbot.features.ai.providers.openrouter.Agent',
            return_value=agent,
        ) as agent_cls,
    ):
        [
            chunk
            async for chunk in streamer.stream_response(
                llm_model='test-model',
                query=make_query(('user', 'hello')),
                ctx=LLMRequestContext(),
                base_labels={},
            )
        ]

    agent_cls.assert_called_once_with(
        provider,
        max_iterations=4,
        max_tool_calls=8,
        total_timeout=60.0,
        memory=memory_cls.return_value,
    )


@pytest.mark.asyncio
async def test_provider_is_closed() -> None:
    """The provider should be closed after the request."""
    streamer, _ = make_streamer()

    provider = make_provider()
    agent = MagicMock()
    agent.run = AsyncMock(
        return_value=SimpleNamespace(text='response'),
    )

    with (
        patch(
            'poxbot.features.ai.providers.openrouter.OpenRouterProvider',
            return_value=provider,
        ),
        patch(
            'poxbot.features.ai.providers.openrouter.Agent',
            return_value=agent,
        ),
    ):
        [
            chunk
            async for chunk in streamer.stream_response(
                llm_model='test-model',
                query=make_query(('user', 'hello')),
                ctx=LLMRequestContext(),
                base_labels={},
            )
        ]

    provider.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_provider_is_closed_when_agent_fails() -> None:
    """The provider should be closed when Agent.run raises."""
    streamer, _ = make_streamer()

    provider = make_provider()
    agent = MagicMock()
    agent.run = AsyncMock(side_effect=RuntimeError('agent failed'))

    with (
        patch(
            'poxbot.features.ai.providers.openrouter.OpenRouterProvider',
            return_value=provider,
        ),
        patch(
            'poxbot.features.ai.providers.openrouter.Agent',
            return_value=agent,
        ),
        pytest.raises(RuntimeError, match='agent failed'),
    ):
        [
            chunk
            async for chunk in streamer.stream_response(
                llm_model='test-model',
                query=make_query(('user', 'hello')),
                ctx=LLMRequestContext(),
                base_labels={},
            )
        ]

    provider.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_latency_metric_is_recorded() -> None:
    """A successful response should record response latency."""
    streamer, manager = make_streamer()

    provider = make_provider()
    agent = MagicMock()
    agent.run = AsyncMock(
        return_value=SimpleNamespace(text='response'),
    )

    labels = {
        'provider': 'openrouter',
        'model': 'test-model',
    }

    with (
        patch(
            'poxbot.features.ai.providers.openrouter.OpenRouterProvider',
            return_value=provider,
        ),
        patch(
            'poxbot.features.ai.providers.openrouter.Agent',
            return_value=agent,
        ),
    ):
        [
            chunk
            async for chunk in streamer.stream_response(
                llm_model='test-model',
                query=make_query(('user', 'hello')),
                ctx=LLMRequestContext(),
                base_labels=labels,
            )
        ]
        
    manager._record_metric.assert_awaited_once()

    call = manager._record_metric.await_args
    assert call is not None

    assert call.kwargs['name'] == 'bot_llm_response_latency_seconds'
    assert call.kwargs['m_type'] == 'histogram'
    assert call.kwargs['labels'] == labels
    assert call.kwargs['description'] == (
        'Total latency for LLM responses in seconds'
    )
    assert call.kwargs['value_or_amount'] >= 0.0
