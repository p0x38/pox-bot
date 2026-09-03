from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from ...persistence.models.guild_settings_v2 import MarkovModelScope

Token = str
State = tuple[Token, ...]


@dataclass(frozen=True, slots=True)
class MarkovModelKey:
    scope: MarkovModelScope
    scope_id: int

    @classmethod
    def global_model(cls) -> MarkovModelKey:
        return cls(MarkovModelScope.GLOBAL, 0)

    @classmethod
    def server(cls, guild_id: int) -> MarkovModelKey:
        return cls(MarkovModelScope.SERVER, guild_id)

    @classmethod
    def user(cls, user_id: int) -> MarkovModelKey:
        return cls(MarkovModelScope.USER, user_id)


@dataclass(frozen=True, slots=True)
class MarkovGenerationResult:
    """Result of generating a response from a Markov model."""

    response: str
    key: MarkovModelKey


def resolve_model_key(
    scope: MarkovModelScope,
    *,
    guild_id: int | None = None,
    user_id: int | None = None,
) -> MarkovModelKey:
    match scope:
        case MarkovModelScope.GLOBAL:
            return MarkovModelKey.global_model()

        case MarkovModelScope.SERVER:
            if guild_id is None:
                raise ValueError('Server Markov scope requires a guild ID.')

            return MarkovModelKey.server(guild_id)

        case MarkovModelScope.USER:
            if user_id is None:
                raise ValueError('User Markov scope requires a user ID.')

            return MarkovModelKey.user(user_id)

        case _:
            raise ValueError(f'Unsupported Markov model scope: {scope!r}')


class MarkovModel:
    """An n-order Markov chain."""

    START = '<START>'
    END = '<END>'

    def __init__(self, order: int = 2):
        if order < 1:
            raise ValueError('order must be >= 1')

        self.order = order

        self.transitions: dict[
            State,
            Counter[Token],
        ] = defaultdict(Counter)

        self.message_count = 0
        self.token_count = 0

    @property
    def state_count(self) -> int:
        """Return the number of states in the model."""
        return len(self.transitions)

    def train(self, tokens: Iterable[str]) -> None:
        """Train the model on a single message."""
        token_list = list(tokens)

        if not token_list:
            return

        padded = [self.START] * self.order + token_list + [self.END]

        for index in range(
            len(padded) - self.order,
        ):
            state = tuple(
                padded[index : index + self.order],
            )

            next_token = padded[index + self.order]

            self.transitions[state][next_token] += 1

        self.message_count += 1
        self.token_count += len(token_list)

    def get_transitions(
        self,
        state: State,
    ) -> Counter[Token]:
        """Return possible next tokens for a state."""
        return self.transitions.get(
            state,
            Counter(),
        )

    def clear(self) -> None:
        """Clear the model."""
        self.transitions.clear()
        self.message_count = 0
        self.token_count = 0

    def __len__(self) -> int:
        """Return number of learned states."""
        return len(self.transitions)
