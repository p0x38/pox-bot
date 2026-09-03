"""Tests for the Pygent-backed OpenRouter adapter."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add src to path to allow imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from poxbot.features.ai.providers.openrouter import OpenRouterStreamer
from poxbot.features.ai.request_context import LLMRequestContext
from poxbot.shared.exceptions.ai_error import InvalidQueryData


def _make_streamer() -> OpenRouterStreamer:
    """Build an OpenRouterStreamer with a mocked manager."""
    manager = MagicMock()
    manager._record_metric = AsyncMock()
    return OpenRouterStreamer(manager, api_key='test-key')


@pytest.mark.asyncio
async def test_invalid_query_is_rejected() -> None:
    """Non-list and empty queries must be rejected before agent execution."""
    streamer = _make_streamer()

    for query in ('not a list', []):
        with pytest.raises(InvalidQueryData):
            async for _ in streamer.stream_response(
                llm_model='gpt-4o',
                query=query,
                ctx=LLMRequestContext(),
                base_labels={},
            ):
                pass


@pytest.mark.asyncio
async def test_invalid_message_is_rejected() -> None:
    """Malformed message data must be converted to InvalidQueryData."""
    streamer = _make_streamer()

    with patch(
        'poxbot.features.ai.providers.openrouter.Message.model_validate',
        side_effect=ValueError('invalid message'),
    ):
        with pytest.raises(InvalidQueryData):
            async for _ in streamer.stream_response(
                llm_model='gpt-4o',
                query=[{'role': 'user', 'content': 'hello'}],
                ctx=LLMRequestContext(),
                base_labels={},
            ):
                pass


@pytest.mark.asyncio
async def test_response_is_generated_through_pygent() -> None:
    """A valid query should run an Agent and yield its response text."""
    streamer = _make_streamer()
    user_message = SimpleNamespace(role='user', content='hello')
    response = SimpleNamespace(text='Hello from Pygent')
    agent = MagicMock()
    agent.run = AsyncMock(return_value=response)
    provider = MagicMock()
    provider.aclose = AsyncMock()

    with (
        patch(
            'poxbot.features.ai.providers.openrouter.Message.model_validate',
            side_effect=lambda item: user_message,
        ) as validate,
        patch(
            'poxbot.features.ai.providers.openrouter.ConversationMemory',
        ) as memory_cls,
        patch(
            'poxbot.features.ai.providers.openrouter.OpenRouterProvider',
            return_value=provider,
        ) as provider_cls,
        patch(
            'poxbot.features.ai.providers.openrouter.Agent',
            return_value=agent,
        ) as agent_cls,
    ):
        result = [
            piece
            async for piece in streamer.stream_response(
                llm_model='gpt-4o',
                query=[{'role': 'user', 'content': 'hello'}],
                ctx=LLMRequestContext(),
                base_labels={'provider': 'openrouter', 'model': 'gpt-4o'},
            )
        ]

    assert result == ['Hello from Pygent']
    validate.assert_called_once_with({'role': 'user', 'content': 'hello'})
    memory_cls.assert_called_once_with(conversation_id='pox-bot')
    provider_cls.assert_called_once_with(
        'gpt-4o',
        api_key='test-key',
        app_name='pox-bot',
    )
    agent_cls.assert_called_once_with(
        provider,
        max_iterations=4,
        max_tool_calls=8,
        total_timeout=60.0,
        memory=memory_cls.return_value,
    )
    agent.run.assert_awaited_once_with(user_message)
    provider.aclose.assert_awaited_once()
    streamer.mgr._record_metric.assert_awaited_once()


@pytest.mark.asyncio
async def test_history_is_seeded_into_conversation_memory() -> None:
    """Messages before the final message should be seeded as conversation history."""
    streamer = _make_streamer()
    history = [
        SimpleNamespace(role='user', content='first'),
        SimpleNamespace(role='assistant', content='second'),
    ]
    last_message = SimpleNamespace(role='user', content='third')
    messages = [*history, last_message]
    response = SimpleNamespace(text='reply')
    agent = MagicMock()
    agent.run = AsyncMock(return_value=response)
    provider = MagicMock()
    provider.aclose = AsyncMock()
    memory = MagicMock()

    with (
        patch(
            'poxbot.features.ai.providers.openrouter.Message.model_validate',
            side_effect=messages,
        ),
        patch(
            'poxbot.features.ai.providers.openrouter.ConversationMemory',
            return_value=memory,
        ),
        patch(
            'poxbot.features.ai.providers.openrouter.OpenRouterProvider',
            return_value=provider,
        ),
        patch('poxbot.features.ai.providers.openrouter.Agent', return_value=agent),
    ):
        result = [
            piece
            async for piece in streamer.stream_response(
                llm_model='gpt-4o',
                query=[
                    {'role': 'user', 'content': 'first'},
                    {'role': 'assistant', 'content': 'second'},
                    {'role': 'user', 'content': 'third'},
                ],
                ctx=LLMRequestContext(),
                base_labels={},
            )
        ]

    assert result == ['reply']
    memory.seed.assert_called_once_with(history)
    agent.run.assert_awaited_once_with(last_message)


@pytest.mark.asyncio
async def test_agent_error_is_propagated_and_provider_is_closed() -> None:
    """Agent failures should propagate while the provider is still closed."""
    streamer = _make_streamer()
    agent = MagicMock()
    agent.run = AsyncMock(side_effect=RuntimeError('generation failed'))
    provider = MagicMock()
    provider.aclose = AsyncMock()

    with (
        patch(
            'poxbot.features.ai.providers.openrouter.Message.model_validate',
            return_value=SimpleNamespace(role='user', content='hello'),
        ),
        patch(
            'poxbot.features.ai.providers.openrouter.OpenRouterProvider',
            return_value=provider,
        ),
        patch('poxbot.features.ai.providers.openrouter.Agent', return_value=agent),
        pytest.raises(RuntimeError, match='generation failed'),
    ):
        async for _ in streamer.stream_response(
            llm_model='gpt-4o',
            query=[{'role': 'user', 'content': 'hello'}],
            ctx=LLMRequestContext(),
            base_labels={},
        ):
            pass

    provider.aclose.assert_awaited_once()
    streamer.mgr._record_metric.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_response_does_not_record_metric() -> None:
    """An empty model response should not yield text or record TTFT."""
    streamer = _make_streamer()
    agent = MagicMock()
    agent.run = AsyncMock(return_value=SimpleNamespace(text=''))
    provider = MagicMock()
    provider.aclose = AsyncMock()

    with (
        patch(
            'poxbot.features.ai.providers.openrouter.Message.model_validate',
            return_value=SimpleNamespace(role='user', content='hello'),
        ),
        patch(
            'poxbot.features.ai.providers.openrouter.OpenRouterProvider',
            return_value=provider,
        ),
        patch('poxbot.features.ai.providers.openrouter.Agent', return_value=agent),
    ):
        result = [
            piece
            async for piece in streamer.stream_response(
                llm_model='gpt-4o',
                query=[{'role': 'user', 'content': 'hello'}],
                ctx=LLMRequestContext(),
                base_labels={},
            )
        ]

    assert result == []
    provider.aclose.assert_awaited_once()
    streamer.mgr._record_metric.assert_not_awaited()
