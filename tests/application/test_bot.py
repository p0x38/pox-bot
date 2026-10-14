from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from discord import (
    HTTPException,
    Intents,
    Interaction,
    InteractionType,
    Message,
    TextChannel,
    app_commands,
)
from discord.ext import commands
from sqlalchemy.exc import SQLAlchemyError

from poxbot.application import ApplicationContext, PoxBot


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
async def bot(mock_config, mock_logger, mock_managers):  # ruff: ignore[unused-async]
    """Provide a pre-instantiated PoxBot instance for test cases."""

    context = MagicMock(spec=ApplicationContext)
    context.settings = mock_config
    context.logger = mock_logger
    context.i18n = mock_managers

    return PoxBot(
        context=context,
        command_prefix=mock_config.bot_prefix,
        intents=Intents.default(),
    )


@pytest.mark.asyncio
async def test_bot_initialization(bot):  # ruff: ignore[unused-async]
    """Verify default tracking properties and configurations setup accurately."""
    assert bot.should_restart is False
    assert bot.settings.bot_prefix == '!'
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
async def test_on_command_error_logs_send_failure(bot, caplog):
    ctx = MagicMock()
    ctx.command = 'broken'
    ctx.guild = None
    ctx.reply = AsyncMock(
        side_effect=HTTPException(MagicMock(status=500, reason='failed'), 'failed'),
    )
    bot.internal_translator.T.return_value = 'Something went wrong'

    await bot.on_command_error(ctx, commands.CommandError('command failed'))

    assert 'Could not send error embed for command broken' in caplog.text
    assert '500 failed' in caplog.text


@pytest.mark.asyncio
async def test_tree_error_uses_safe_fallback_if_locale_and_translation_are_missing(bot):
    bot.get_locale = AsyncMock(side_effect=SQLAlchemyError('database unavailable'))
    bot.internal_translator.T.side_effect = lambda key, *_args, **_kwargs: key
    bot.try_return_error = AsyncMock()

    interaction = MagicMock(spec=Interaction)
    interaction.type = InteractionType.application_command
    interaction.command.qualified_name = 'test command'
    interaction.user.mention = '<@123>'
    interaction.locale = 'en-US'

    await bot._on_tree_error(
        interaction,
        app_commands.CommandInvokeError(
            MagicMock(),
            RuntimeError('private traceback details'),
        ),
    )

    sent_embed = bot.try_return_error.call_args.kwargs['embed']
    assert sent_embed.title == 'Error'
    assert 'Something went wrong' in sent_embed.description
    assert 'private traceback details' not in sent_embed.description


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
        'discord.ext.commands.AutoShardedBot.close',
        new_callable=AsyncMock,
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
async def test_format_channel_info_with_guild_text_channel(bot):  # ruff: ignore[unused-async]
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

    result = bot.format_channel_info(channel)

    assert 'My Guild - general (9999)' in result
