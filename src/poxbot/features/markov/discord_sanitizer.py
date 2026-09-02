from __future__ import annotations

import re


DISCORD_MENTION_PATTERN = re.compile(r'<(?:@!?|@&|#)\d+>')


def sanitize_discord_mentions(text: str) -> str:
    """Remove Discord user, role, and channel mentions from message text."""
    if not text:
        return ''

    return ' '.join(DISCORD_MENTION_PATTERN.sub('', text).split())
