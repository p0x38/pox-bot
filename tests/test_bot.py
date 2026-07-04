from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from discord import Intents, Interaction, Message, TextChannel

from src.core.bot import PoxBot


@pytest.fixture
def mock_config():
    """Create a mock configuration instance matching BotSettings fields."""
    config = MagicMock()
    config.trace_config.enabled = False
    config.database_config.build_url.return_value = (
        'postgresql://user:pass@localhost/db'
    )
    config.bot_prefix = '!'
    return config


@pytest.fixture
def mock_logger():
    """Create a standard mock logger instance."""
    return MagicMock()


@pytest.fixture
def mock_managers():
    """Create a tiered mock instance for translation managers."""
    manager = MagicMock()
    manager.internal = MagicMock()
    manager.discord = MagicMock()
    return manager


@pytest.fixture
async def bot(mock_config, mock_logger, mock_managers):
    """Provide a pre-instantiated PoxBot instance for test cases."""
    return PoxBot(
        command_prefix=mock_config.bot_prefix,
        config=mock_config,
        logger=mock_logger,
        translation_manager=mock_managers,
        discord_translator=mock_managers.discord,
        internal_translator=mock_managers.internal,
        intents=Intents.default(),
    )


@pytest.mark.asyncio
async def test_bot_initialization(bot):
    """Verify default tracking properties and configurations setup accurately."""
    assert bot.should_restart is False
    assert bot.config.bot_prefix == '!'
    assert bot.metrics is None


@pytest.mark.asyncio
async def test_try_return_error_when_response_is_done(bot):
    """Verify error responses route cleanly into a follow-up message channel."""
    interaction = MagicMock(spec=Interaction)
    interaction.response.is_done.return_value = True
    interaction.followup.send = AsyncMock()

    await bot.try_return_error(interaction, content='An error occurred!')
    interaction.followup.send.assert_called_once_with(content='An error occurred!')


@pytest.mark.asyncio
async def test_try_return_error_when_response_not_done(bot):
    """Verify error responses route cleanly into an original response block."""
    interaction = MagicMock(spec=Interaction)
    interaction.response.is_done.return_value = False
    interaction.response.send_message = AsyncMock()

    await bot.try_return_error(interaction, content='An error occurred!')
    interaction.response.send_message.assert_called_once_with(
        content='An error occurred!',
    )


@pytest.mark.asyncio
async def test_bot_on_message_ignores_self_or_everyone(bot):
    """Ensure automated prefix tracking ignores systemic notification hooks."""
    bot.statistics.count_prefix_command = MagicMock()

    mock_bot_user = MagicMock()
    mock_bot_user.id = 12345
    type(bot).user = PropertyMock(return_value=mock_bot_user)

    message_from_self = MagicMock(spec=Message)
    message_from_self.author = mock_bot_user
    message_from_self.mention_everyone = False

    await bot.on_message(message_from_self)
    bot.statistics.count_prefix_command.assert_not_called()


@pytest.mark.asyncio
async def test_bot_close(bot):
    """Verify that all internal managers and database connections close gracefully."""
    bot.database = MagicMock()
    bot.database.close = AsyncMock()
    bot.resources = MagicMock()
    bot.resources.close = AsyncMock()
    bot.counter_manager = MagicMock()
    bot.counter_manager.save_async = AsyncMock()

    with patch(
        'discord.ext.commands.AutoShardedBot.close', new_callable=AsyncMock,
    ) as mock_super_close:
        await bot.close()

        bot.counter_manager.save_async.assert_called_once()
        bot.database.close.assert_called_once()
        bot.resources.close.assert_called_once()
        mock_super_close.assert_called_once()


def test_format_channel_info_null_channel(bot):
    """Verify safe fallback strings when evaluating unresolvable Discord channels."""
    result = bot.format_channel_info(None)
    assert result == 'Null channel type'


@pytest.mark.asyncio
async def test_format_channel_info_with_guild_text_channel(bot):
    """Verify formatting structures safely merge guild text identities."""

    class DummyTextChannel(TextChannel):
        def __init__(self):
            self.name = 'general'
            self.id = 9999
            self.guild = MagicMock()
            self.guild.name = 'My Guild'

    channel = MagicMock(spec=DummyTextChannel)
    channel.name = 'general'
    channel.id = 9999
    channel.guild.name = 'My Guild'

    with patch('src.core.bot.isinstance', create=True, return_value=True):
        result = bot.format_channel_info(channel)

    assert 'My Guild - general (9999)' in result
