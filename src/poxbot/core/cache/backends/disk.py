import contextlib
import hashlib
import math
import uuid
from pathlib import Path

import orjson

from ..entry import CacheEntry
from ..protocols import CacheEntry as CacheEntryType
from ..protocols import CacheKey, Serializer

_CACHE_FORMAT_VERSION = 1


class DiskBackend:
    def __init__(
        self,
        directory: Path,
        namespace: str,
        serializer: Serializer,
    ) -> None:
        namespace_id = hashlib.sha256(
            namespace.encode('utf-8'),
        ).hexdigest()[:16]

        self.directory = directory / namespace_id
        self.serializer = serializer
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path_for(self, key: CacheKey) -> Path:
        identity = orjson.dumps([type(key).__qualname__, key])
        digest = hashlib.sha256(identity).hexdigest()[:32]

        return self.directory / f'{digest}.cache'

    @staticmethod
    def _discard(path: Path) -> None:
        with contextlib.suppress(OSError):
            path.unlink(missing_ok=True)

    def get_entry(self, key: CacheKey) -> CacheEntryType | None:
        path = self._path_for(key)

        try:
            payload = path.read_bytes()
        except FileNotFoundError:
            return None

        try:
            record = self.serializer.loads(payload)

            if not isinstance(record, dict):
                raise ValueError('Invalid cache record')

            if (
                record.get('version') != _CACHE_FORMAT_VERSION
                or record.get('key') != key
                or record.get('key_type') != type(key).__qualname__
                or 'value' not in record
            ):
                raise ValueError('Incompatible cache record')

            stored_at = record.get('stored_at')
            expires_at = record.get('expires_at')
            priority = record.get('priority', 0)

            if (
                isinstance(stored_at, bool)
                or not isinstance(stored_at, (int, float))
                or not math.isfinite(stored_at)
            ):
                raise ValueError('Invalid cache timestamp')

            if expires_at is not None and (
                isinstance(expires_at, bool)
                or not isinstance(expires_at, (int, float))
                or not math.isfinite(expires_at)
            ):
                raise ValueError('Invalid expiration timestamp')

            if (
                isinstance(priority, bool)
                or not isinstance(priority, int)
            ):
                raise ValueError('Invalid cache priority')

            return CacheEntry(
                value=record['value'],
                stored_at=float(stored_at),
                expires_at=(
                    float(expires_at)
                    if expires_at is not None
                    else None
                ),
                priority=priority,
            )

        except Exception:
            self._discard(path)
            return None

    def set_entry(
        self,
        key: CacheKey,
        entry: CacheEntry,
    ) -> None:
        path = self._path_for(key)

        payload = self.serializer.dumps(
            {
                'version': _CACHE_FORMAT_VERSION,
                'key': key,
                'key_type': type(key).__qualname__,
                'stored_at': entry.stored_at,
                'expires_at': entry.expires_at,
                'priority': entry.priority,
                'value': entry.value,
            },
        )

        temporary_path = self.directory / f'.{uuid.uuid4().hex}.tmp'

        try:
            temporary_path.parent.mkdir(parents=True, exist_ok=True)

            with temporary_path.open('wb') as stream:
                stream.write(payload)

            temporary_path.replace(path)
        finally:
            temporary_path.unlink(missing_ok=True)

    def delete(self, key: CacheKey) -> None:
        self._discard(self._path_for(key))

    def clear(self) -> None:
        for path in self.directory.glob('*.cache'):
            self._discard(path)
            