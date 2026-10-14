import time
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CacheEntry:
    value: object
    stored_at: float
    expires_at: float | None
    priority: int = 0

    def is_expired(self) -> bool:
        return (
            self.expires_at is not None
            and time.time() >= self.expires_at
        )
    