from discord import User


class AntiSpamManager:
    def __init__(
        self,
        time_window: int = 5,
        max_messages_per_window: int = 5,
    ):
        self.time_window = time_window
        self.max_messages_per_window = max_messages_per_window

        self.user_message_timestamps: dict[int, list[float]] = {}

    def record_message(self, user: User):
        pass  # TODO: implement the function

    def is_spamming(self, user: User) -> bool:
        return False  # TODO: implement the function
