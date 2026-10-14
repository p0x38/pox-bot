from collections import OrderedDict
from threading import RLock

from ..entry import CacheEntry
from ..protocols import CacheKey


class MemoryBackend:
    def __init__(self, max_entries: int = 1024) -> None:
        if max_entries < 1:
            raise ValueError('max_entries must be positive')

        self._max_entries = max_entries
        self._entries: OrderedDict[CacheKey, CacheEntry] = (
            OrderedDict()
        )
        self._lock = RLock()

    def get_entry(self, key: CacheKey) -> CacheEntry | None:
        with self._lock:
            entry = self._entries.get(key)

            if entry is not None:
                self._entries.move_to_end(key)

            return entry

    def set_entry(self, key: CacheKey, entry: CacheEntry) -> None:
        with self._lock:
            self._entries[key] = entry
            self._entries.move_to_end(key)

            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)

    def delete(self, key: CacheKey) -> None:
        with self._lock:
            self._entries.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def snapshot(self) -> list[tuple[CacheKey, CacheEntry]]:
        with self._lock:
            return list(self._entries.items())
        