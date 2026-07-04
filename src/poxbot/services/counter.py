import asyncio
from pathlib import Path
from typing import Any

import aiofiles
import orjson
from discord import DMChannel, GroupChannel, Guild
from discord.abc import GuildChannel


class CounterManager:
    def __init__(self, file_path: Path):
        self.file_path = file_path

        self._counters: dict[str, int] = {}
        self._lock = asyncio.Lock()

    def increment(self, name: str, amount: int = 1) -> None:
        if name not in self._counters:
            self._counters[name] = 0
        self._counters[name] += amount

    def increment_interaction(self, target: Any, amount: int = 1) -> None:
        if isinstance(target, Guild):
            key = f'interactions:guild:{target.id}'
        elif (
            isinstance(target, GuildChannel)
            or (hasattr(target, 'guild')
            and target.guild)
        ):
            key = f'interactions:guild:{target.guild.id}'
        elif isinstance(target, DMChannel):
            key = f'interactions:dm:{target.id}'
        elif isinstance(target, GroupChannel):
            key = f'interactions:group:{target.id}'
        elif isinstance(target, (int, str)):
            key = f'interactions:{target}'
        else:
            target_id = getattr(target, 'id', 'unknown')
            key = f'interactions:unknown:{target_id}'

        self.increment(key, amount)

    def increment_guild(self, guild: Guild, amount: int = 1) -> None:
        key = f'messages:{guild.id}'
        self.increment(key, amount)

    def get_guild_count(self, guild: Guild) -> int:
        key = f'messages:{guild.id}'
        return self._counters.get(key, 0)

    def get_interaction_count(self, target_id_or_obj: Any) -> int:
        if isinstance(target_id_or_obj, Guild):
            return self._counters.get(f'interactions:guild:{target_id_or_obj.id}', 0)
        if isinstance(target_id_or_obj, DMChannel):
            return self._counters.get(f'interactions:dm:{target_id_or_obj.id}', 0)
        if isinstance(target_id_or_obj, GroupChannel):
            return self._counters.get(f'interactions:group:{target_id_or_obj.id}', 0)
        return self._counters.get(f'interactions:{target_id_or_obj}', 0)

    def get_count(self, name: str) -> int:
        return self._counters.get(name, 0)

    async def load_async(self) -> None:
        if not self.file_path.exists():
            return

        async with self._lock:
            try:
                async with aiofiles.open(self.file_path, 'rb') as f:
                    content = await f.read()
                    if not content:
                        return

                    loaded_data = orjson.loads(content)
                    if isinstance(loaded_data, dict):
                        self._counters = {
                            str(k): int(v) for k, v in loaded_data.items()
                        }
            except (orjson.JSONDecodeError, OSError, ValueError):
                pass

    async def save_async(self) -> None:
        async with self._lock:
            try:
                self.file_path.parent.mkdir(parents=True, exist_ok=True)

                binary_data = orjson.dumps(self._counters)

                async with aiofiles.open(self.file_path, 'wb') as f:
                    await f.write(binary_data)
            except OSError:
                pass
