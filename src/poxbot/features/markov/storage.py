from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Protocol

from .model import MarkovModel


class MarkovStorage(Protocol):
    """Persistence interface for Markov models."""

    async def load(
        self,
        guild_id: int,
        model: MarkovModel,
    ) -> None: ...

    async def save_transition(
        self,
        guild_id: int,
        state: Sequence[str],
        next_token: str,
        count: int,
    ) -> None: ...


class InMemoryMarkovStorage:
    """Simple in-memory storage.

    Useful for development/testing before connecting PostgreSQL.
    """

    def __init__(self):
        self.data: dict[
            int,
            dict[tuple[str, ...], Counter[str]],
        ] = {}

    async def load(
        self,
        guild_id: int,
        model: MarkovModel,
    ) -> None:
        model.clear()

        guild_data = self.data.get(guild_id)

        if not guild_data:
            return

        for state, transitions in guild_data.items():
            model.transitions[state].update(
                transitions,
            )

    async def save_transition(
        self,
        guild_id: int,
        state: Sequence[str],
        next_token: str,
        count: int,
    ) -> None:
        guild_data = self.data.setdefault(
            guild_id,
            {},
        )

        state_tuple = tuple(state)

        transitions = guild_data.setdefault(
            state_tuple,
            Counter(),
        )

        transitions[next_token] = count
