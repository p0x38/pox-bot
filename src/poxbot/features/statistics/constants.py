from typing import Final

from ...persistence.models.pydantic.blacklisted_item import (
    BlacklistItem,
    BlacklistReason,
)


class BotConstants:
    def __init__(self):
        self.max_servers: Final[int] = 90
        self.exclude_extensions: Final[list[str]] = [
            'chat',
            'eew',
            'log',
            'others',
            'websockets',
        ]
        self.scary_mode: bool = False
        self.whitelisted_domains: set[str] = {
            'klipy.co',
            'klipy.com',
            'kixpy.com',
            'txnor.com',
            'giphy.com',
            'tenor.com',
            'youtube.com',
            'x.com',
            'youtu.be',
            'twitch.tv',
            'spotify.com',
            'soundcloud.com',
            'github.com',
            'reddit.com',
        }
        builtin_blacklisted_data = [
            {
                'value': 'grabify.link',
                'reasons': {BlacklistReason.IP_LOGGER: 'IP Grabber'},
            },
            {
                'value': 'iplogger.org',
                'reasons': {BlacklistReason.IP_LOGGER: 'IP Logger'},
            },
            {
                'value': 'bit.ly',
                'reasons': {BlacklistReason.URL_SHORTENER: 'URL Shortener'},
            },
            {
                'value': 'tinyurl.com',
                'reasons': {BlacklistReason.URL_SHORTENER: 'URL Shortener'},
            },
            {
                'value': 'unknown-scam.com'  # 理由なし
            },
        ]
        self.blacklisted_domains: set[BlacklistItem] = {
            BlacklistItem(item) for item in builtin_blacklisted_data
        }
