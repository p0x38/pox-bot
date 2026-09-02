from __future__ import annotations

import random

from .model import MarkovModel, State
from .tokenizer import MarkovTokenizer


class MarkovGenerator:
    def __init__(
        self,
        model: MarkovModel,
        tokenizer: MarkovTokenizer | None = None,
    ):
        self.model = model
        self.tokenizer = tokenizer or MarkovTokenizer()

    def _start_state(self) -> State:
        return (self.model.START,) * self.model.order

    def generate(
        self,
        *,
        max_tokens: int = 50,
        seed: str | None = None,
    ) -> str:
        if max_tokens <= 0:
            return ''

        if self.model.message_count <= 0:
            return ''

        if seed:
            seed_tokens = self.tokenizer.tokenize(seed)

            if seed_tokens:
                state = tuple(
                    seed_tokens[-self.model.order :],
                )
            else:
                state = self._start_state()
        else:
            state = self._start_state()

        generated: list[str] = []

        for _ in range(max_tokens):
            transitions = self.model.get_transitions(state)

            if not transitions:
                state = self._start_state()
                transitions = self.model.get_transitions(state)

            if not transitions:
                break

            tokens = list(transitions.keys())
            weights = list(transitions.values())

            token = random.choices(
                tokens,
                weights=weights,
                k=1,
            )[0]

            if token == self.model.END:
                break

            generated.append(token)

            state = (
                *state[1:],
                token,
            )

        return self.tokenizer.detokenize(generated)
