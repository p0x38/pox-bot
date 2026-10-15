from __future__ import annotations

import math
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from threading import RLock
from typing import TypeVar, cast

from .backends.disk import DiskBackend
from .backends.memory import MemoryBackend
from .entry import CacheEntry
from .protocols import CacheBackend, CacheKey, Serializer
from .serializers import OrjsonSerializer

T = TypeVar('T')


class _DefaultTTL:
    __slots__ = ()


_DEFAULT_TTL = _DefaultTTL()


class Cache:
    def __init__(
        self,
        ttl: float | None = None,
        *,
        directory: str | Path | None = None,
        temporary: bool = False,
        namespace: str = 'default',
        max_memory_entries: int = 1024,
        serializer: Serializer | None = None,
    ) -> None:
        self._validate_ttl(ttl)

        if not namespace.strip():
            raise ValueError('namespace must not be empty')

        self.ttl = ttl
        self.namespace = namespace
        self._memory = MemoryBackend(max_memory_entries)
        self._disk: CacheBackend | None = None
        self._lock = RLock()
        self._closed = False

        self._temporary_directory: tempfile.TemporaryDirectory[str] | None = None
        self.directory: Path | None = None

        root: Path | None

        if temporary:
            parent = Path(directory) if directory is not None else None

            if parent is not None:
                parent.mkdir(parents=True, exist_ok=True)

            self._temporary_directory = tempfile.TemporaryDirectory(
                prefix='poxbot-cache-',
                dir=parent,
            )
            root = Path(self._temporary_directory.name)

        elif directory is not None:
            root = Path(directory)

        else:
            root = None

        if root is not None:
            disk = DiskBackend(
                directory=root,
                namespace=namespace,
                serializer=serializer or OrjsonSerializer(),
            )
            self._disk = disk
            self.directory = disk.directory

    @staticmethod
    def _validate_ttl(ttl: float | None) -> None:
        if ttl is not None and (
            isinstance(ttl, bool)
            or not isinstance(ttl, (int, float))
            or not math.isfinite(ttl)
            or ttl < 0
        ):
            raise ValueError('ttl must be finite and non-negative')

    @staticmethod
    def _validate_key(key: CacheKey) -> None:
        if type(key) not in (str, int):
            raise TypeError('Cache keys must be strings or integers')

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError('Cache is closed')

    def _delete_unlocked(self, key: CacheKey) -> None:
        self._memory.delete(key)

        if self._disk is not None:
            self._disk.delete(key)

    def _get_entry_unlocked(
        self,
        key: CacheKey,
    ) -> CacheEntry | None:
        entry = self._memory.get_entry(key)

        if entry is not None:
            if not entry.is_expired():
                return entry

            self._memory.delete(key)

        if self._disk is None:
            return None

        entry = self._disk.get_entry(key)

        if entry is None:
            return None

        if entry.is_expired():
            self._disk.delete(key)
            return None

        self._memory.set_entry(key, entry)
        return entry

    def get(
        self,
        key: CacheKey,
        default: T | None = None,
    ) -> T | None:
        self._validate_key(key)

        with self._lock:
            self._ensure_open()
            entry = self._get_entry_unlocked(key)

            if entry is None:
                return default

            return cast(T, entry.value)

    def set(
        self,
        key: CacheKey,
        value: object,
        priority: int = 0,
        *,
        ttl: float | _DefaultTTL | None = _DEFAULT_TTL,
    ) -> None:
        self._validate_key(key)

        effective_ttl = self.ttl if isinstance(ttl, _DefaultTTL) else ttl
        self._validate_ttl(effective_ttl)

        if isinstance(priority, bool) or not isinstance(priority, int):
            raise ValueError('priority must be an integer')

        stored_at = time.time()
        entry = CacheEntry(
            value=value,
            stored_at=stored_at,
            expires_at=(
                stored_at + effective_ttl if effective_ttl is not None else None
            ),
            priority=priority,
        )

        with self._lock:
            self._ensure_open()

            if self._disk is not None:
                self._disk.set_entry(key, entry)

            self._memory.set_entry(key, entry)

    def get_or_set(
        self,
        key: CacheKey,
        factory: Callable[[], T],
        *,
        ttl: float | _DefaultTTL | None = _DEFAULT_TTL,
    ) -> T:
        self._validate_key(key)

        with self._lock:
            self._ensure_open()
            entry = self._get_entry_unlocked(key)

            if entry is not None:
                return cast(T, entry.value)

        value = factory()
        self.set(key, value, ttl=ttl)
        return value

    def contains(self, key: CacheKey) -> bool:
        self._validate_key(key)

        with self._lock:
            self._ensure_open()
            return self._get_entry_unlocked(key) is not None

    def delete(self, key: CacheKey) -> None:
        self._validate_key(key)

        with self._lock:
            self._ensure_open()
            self._delete_unlocked(key)

    def clear(self) -> None:
        with self._lock:
            self._ensure_open()
            self._memory.clear()

            if self._disk is not None:
                self._disk.clear()

    def get_cached_time_by_key(
        self,
        key: CacheKey,
    ) -> float | None:
        self._validate_key(key)

        with self._lock:
            self._ensure_open()
            entry = self._get_entry_unlocked(key)
            return entry.stored_at if entry is not None else None

    def get_priority_by_key(self, key: CacheKey) -> int:
        self._validate_key(key)

        with self._lock:
            self._ensure_open()
            entry = self._get_entry_unlocked(key)
            return entry.priority if entry is not None else -1

    def get_all(self) -> dict[CacheKey, dict[str, object]]:
        with self._lock:
            self._ensure_open()
            result: dict[CacheKey, dict[str, object]] = {}

            for key, entry in self._memory.snapshot():
                if entry.is_expired():
                    self._memory.delete(key)
                    continue

                result[key] = {
                    'value': entry.value,
                    'time': entry.stored_at,
                    'priority': entry.priority,
                }

            return result

    def get_count(self) -> int:
        return len(self.get_all())

    def get_front(self) -> dict[str, object] | None:
        entries = self.get_all()
        return next(iter(entries.values()), None)

    def get_rear(self) -> dict[str, object] | None:
        entries = self.get_all()

        if not entries:
            return None

        return next(reversed(entries.values()))

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return

            self._closed = True
            self._memory.clear()

            if self._temporary_directory is not None:
                self._temporary_directory.cleanup()

    def __enter__(self) -> 'Cache':
        self._ensure_open()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
