from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol


class MarkovBackend(Protocol):
    """Backend interface for Markov training and generation."""

    @property
    def message_count(self) -> int: ...

    def train(self, tokens: Iterable[str]) -> None: ...

    def generate_tokens(
        self,
        *,
        max_tokens: int = 50,
        seed: str | None = None,
    ) -> list[str]: ...

    def clear(self) -> None: ...
