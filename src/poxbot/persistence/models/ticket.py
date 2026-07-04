from dataclasses import asdict, dataclass, field
from datetime import datetime

from pytz import UTC


@dataclass
class TicketData:
    channel_id: int
    user_id: int
    guild_id: int
    opened_at: float = field(default_factory=lambda: datetime.now(UTC).timestamp())
    status: str = 'open'

    @classmethod
    def from_row(cls, row) -> 'TicketData | None':
        if not row:
            return None

        return cls(
            channel_id=row['channel_id'],
            user_id=row['user_id'],
            guild_id=row['guild_id'],
            opened_at=row['opened_at'],
            status=row['status'],
        )

    def to_dict(self) -> dict:
        return asdict(self)
