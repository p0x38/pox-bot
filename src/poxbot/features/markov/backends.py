from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

import markovify

from .model import MarkovModel, State
from .tokenizer import MarkovTokenizer

MarkovBackendName = Literal['custom', 'markovify']


class CustomMarkovBackend:
    """Use the project's native transition-table implementation."""

    def __init__(self, model: MarkovModel, tokenizer: MarkovTokenizer) -> None:
        self.model = model
        self.tokenizer = tokenizer

    @property
    def message_count(self) -> int:
        return self.model.message_count

    def train(self, tokens: Iterable[str]) -> None:
        self.model.train(tokens)

    def generate_tokens(
        self,
        *,
        max_tokens: int = 50,
        seed: str | None = None,
    ) -> list[str]:
        if max_tokens <= 0 or self.model.message_count <= 0:
            return []

        if seed:
            seed_tokens = self.tokenizer.tokenize(seed)
            state: State = (
                tuple(seed_tokens[-self.model.order :])
                if seed_tokens
                else self._start_state()
            )
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

            tokens = list(transitions)
            weights = list(transitions.values())
            token = markovify.Chain(
                None,
                self.model.order,
                model={state: dict(zip(tokens, weights, strict=True))},
            ).move(state)

            if token == self.model.END:
                break

            generated.append(token)
            state = (*state[1:], token)

        return generated

    def clear(self) -> None:
        self.model.clear()

    def _start_state(self) -> State:
        return (self.model.START,) * self.model.order


class MarkovifyBackend(CustomMarkovBackend):
    """Use Markovify's Chain implementation over the existing model data."""

    _BEGIN = markovify.chain.BEGIN
    _END = markovify.chain.END

    def __init__(self, model: MarkovModel, tokenizer: MarkovTokenizer) -> None:
        super().__init__(model, tokenizer)
        self._chain: markovify.Chain | None = None
        self._chain_signature: tuple[int, int] | None = None

    def train(self, tokens: Iterable[str]) -> None:
        self.model.train(tokens)
        self._invalidate()

    def clear(self) -> None:
        super().clear()
        self._invalidate()

    def generate_tokens(
        self,
        *,
        max_tokens: int = 50,
        seed: str | None = None,
    ) -> list[str]:
        if max_tokens <= 0 or self.model.message_count <= 0:
            return []

        chain = self._get_chain()
        state = self._resolve_seed_state(seed)

        try:
            generated = list(chain.gen(init_state=state))
        except KeyError:
            generated = list(chain.gen())

        return generated[:max_tokens]

    def _get_chain(self) -> markovify.Chain:
        signature = (
            self.model.message_count,
            self.model.state_count,
        )

        if self._chain is not None and self._chain_signature == signature:
            return self._chain

        model: dict[tuple[str, ...], dict[str, int]] = {}

        for state, transitions in self.model.transitions.items():
            markov_state = tuple(
                self._BEGIN if token == self.model.START else token
                for token in state
            )
            markov_transitions = {
                self._END if token == self.model.END else token: count
                for token, count in transitions.items()
            }
            model[markov_state] = markov_transitions

        self._chain = markovify.Chain(
            None,
            self.model.order,
            model=model,
        )
        self._chain_signature = signature
        return self._chain

    def _resolve_seed_state(self, seed: str | None) -> State | None:
        if not seed:
            return None

        tokens = self.tokenizer.tokenize(seed)
        if not tokens:
            return None

        return tuple(tokens[-self.model.order :])

    def _invalidate(self) -> None:
        self._chain = None
        self._chain_signature = None
