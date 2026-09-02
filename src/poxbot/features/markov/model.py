from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable

Token = str
State = tuple[Token, ...]


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
