import string
from datetime import datetime
from random import choices, randint
from time import time
from uuid import UUID, uuid4

import numpy as np
from pytz import UTC

from ...services.counter import CounterManager
from ...shared.utils.app_path import app_dir
from .interaction import InteractionStatistics


class BotStatistics:
    def __init__(self):
        self.bot_launch_datetime: datetime = datetime.now(UTC)
        self.bot_launch_timestamp: float = time()

        self.handled_prefix_commands: int = 0
        self.received_chunks: int = 0

        self.session_uuid: UUID = uuid4()
        self.session_signature: str = ''.join(
            np.random.choice(
                np.fromiter(string.ascii_letters + string.digits, dtype='<U1'),
                size=np.random.randint(4, 7),
            ),
        )

        self.interaction_statistics: InteractionStatistics = InteractionStatistics()

        self.counter_manager = CounterManager(app_dir.user_data_path / 'countdata')

    def count_message(self):
        self.counter_manager.increment('total_messages')

    def regenerate_signature(self):
        self.session_signature = ''.join(
            np.random.choice(
                np.fromiter(string.ascii_letters + string.digits, dtype='<U1'),
                size=np.random.randint(4, 7),
            ),
        )
        return self.session_signature

    def count_prefix_command(self):
        self.counter_manager.increment('handled_prefix_commands')

    @property
    def total_messages(self) -> int:
        return self.counter_manager.get_count('total_messages')
