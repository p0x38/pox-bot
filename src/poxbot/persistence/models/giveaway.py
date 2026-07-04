from dataclasses import asdict, dataclass


@dataclass
class GiveawayData:
    message_id: int
    channel_id: int
    guild_id: int
    end_time: int
    winners: int
    prize: str
    host_id: int

    @classmethod
    def from_row(cls, row) -> 'GiveawayData | None':
        if not row:
            return None

        return cls(
            message_id=row['message_id'],
            channel_id=row['channel_id'],
            guild_id=row['guild_id'],
            end_time=row['end_time'],
            winners=row['winners'],
            prize=row['prize'],
            host_id=row['host_id'],
        )

    def to_dict(self) -> dict:
        return asdict(self)

    def is_expired(self) -> bool:
        from datetime import datetime

        from pytz import UTC

        return self.end_time <= int(datetime.now(UTC).timestamp())
