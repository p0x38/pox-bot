from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from discord import DMChannel, GroupChannel, Guild
from discord.abc import GuildChannel
from discord.ext import tasks

from ..infrastructure.logger.setup import get_logger

if TYPE_CHECKING:
    from ..application.bot import PoxBot


class CounterManager:
    def __init__(self, bot: 'PoxBot'):  # noqa: UP037
        self.logger = get_logger(__name__, prefix='CounterManager')
        self.bot = bot

        self._counters: dict[str, int] = {}
        self._lock = asyncio.Lock()

        self.db_sync_loop.start()

    def increment(self, name: str, amount: int = 1) -> None:
        if name not in self._counters:
            self._counters[name] = 0
        self._counters[name] += amount

    def increment_interaction(self, target: Any, amount: int = 1) -> None:
        if isinstance(target, Guild):
            key = f'interactions:guild:{target.id}'
        elif isinstance(target, GuildChannel) or (
            hasattr(target, 'guild') and target.guild
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

    @tasks.loop(seconds=15.0)
    async def db_sync_loop(self) -> None:
        await self.sync_to_database()

    @db_sync_loop.before_loop
    async def before_db_sync_loop(self) -> None:
        await self.bot.wait_until_ready()

    async def sync_to_database(self) -> None:
        if not self.bot.database.metrics:
            return

        metrics_db = self.bot.database.metrics

        async with self._lock:
            if not self._counters:
                return
            snapshot = self._counters.copy()
            self._counters.clear()

        for key, amount in snapshot.items():
            if amount <= 0:
                continue

            try:
                if key.startswith('interactions:'):
                    parts = key.split(':')
                    if len(parts) >= 3:
                        target_id = parts[2]
                        await metrics_db.increment_interaction(
                            target=target_id, amount=amount,
                        )
                elif key.startswith('messages:'):
                    parts = key.split(':')
                    if len(parts) >= 2:
                        guild_id = parts[1]
                        await metrics_db.increment_message_by_id(
                            guild_id=guild_id, amount=amount,
                        )
            except Exception:
                self.logger.exception(
                    'Exception raised while syncing counters to database',
                )

    async def load_async(self) -> None:
        pass

    async def save_async(self) -> None:
        self.db_sync_loop.cancel()

        await self.sync_to_database()
