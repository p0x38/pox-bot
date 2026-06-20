from dataclasses import field

from attr import dataclass


@dataclass
class UserStats:
    user_id: int
    xp: int = 0
    level: int = 1
    total_messages: int = 0
    
    @classmethod
    def from_row(cls, row):
        if not row:
            return None
        return cls(
            user_id=row['user_id'],
            xp=row['xp'],
            level=row['level'],
            total_messages=row['total_messages']
        )

@dataclass
class LeaderboardItem:
    user_id: int
    xp: int
    level: int
    rank: int | None = None

@dataclass
class LeaderboardData:
    items: list[LeaderboardItem] = field(default_factory=list)
    sort_by: str = "xp"

    @classmethod
    def from_rows(cls, rows, sort_by: str):
        items = [
            LeaderboardItem(
                user_id=row['user_id'],
                xp=row['xp'],
                level=row['level'],
                rank=i + 1
            ) for i, row in enumerate(rows)
        ]
        return cls(items=items, sort_by=sort_by)