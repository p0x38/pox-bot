from datetime import datetime

from discord import Member, User
from pytz import UTC

from ..services.database import DatabaseManager


class AntiSpamManager:
    def __init__(
        self,
        database_manager: DatabaseManager,
        time_window: int = 5,
        max_messages_per_window: int = 5,
    ):
        self.db = database_manager
        self.time_window = time_window
        self.max_messages_per_window = max_messages_per_window

        self.user_message_timestamps: dict[int, list[datetime]] = {}

    def record_message(self, user: User | Member):
        now = datetime.now(UTC)

        if user.id not in self.user_message_timestamps:
            self.user_message_timestamps[user.id] = []

        self.user_message_timestamps[user.id].append(now)

        self.user_message_timestamps[user.id] = [
            ts
            for ts in self.user_message_timestamps[user.id]
            if (now - ts).total_seconds() < self.time_window
        ]

    def is_spamming(self, user: User | Member) -> bool:
        timestamps = self.user_message_timestamps.get(user.id, [])
        return len(timestamps) > self.max_messages_per_window
