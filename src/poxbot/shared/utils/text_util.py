from collections.abc import Callable

from discord import Message


def crop_word(text: str, needle_word: str, padding: int = 8, emphasis: bool = True):
    start = text.lower().find(needle_word.lower())
    if start == -1:
        return None

    needle_len = len(needle_word)

    if emphasis:
        low = max(0, start - padding)
        high = min(len(text), start + needle_len + padding)

        cropped = text[low:high]

        rel_start = start - low

        return (
            cropped[:rel_start]
            + '**'
            + cropped[rel_start : rel_start + needle_len]
            + '**'
            + cropped[rel_start + needle_len :]
        )
    low = max(0, start - padding)
    high = min(len(text), start + needle_len + padding)
    return text[low:high]


def format_discord_message(
    message: Message,
    content_formatter: Callable[[str], str] | None = None,
) -> str:
    """Format a Discord message as a Markdown link."""
    content = (
        content_formatter(message.content)
        if content_formatter is not None
        else message.content
    )

    if message.guild is not None:
        url = (
            f'https://discord.com/channels/'
            f'{message.guild.id}/{message.channel.id}/{message.id}'
        )
        return f'- [{message.created_at:%Y-%m-%d %H:%M:%S}]({url}): {content}'

    return f'- [{message.created_at:%Y-%m-%d %H:%M:%S}] {content}'
