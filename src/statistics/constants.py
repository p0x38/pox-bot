from typing import Final


class BotConstants:
    def __init__(self):
        self.max_servers: Final[int] = 90
        self.exclude_extensions: Final[list[str]] = [
            "chat", "chatbot", "eew",
            "log", "others", "websockets"
        ]
        self.scary_mode: bool = False
