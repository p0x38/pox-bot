from __future__ import annotations

from .backends import CustomMarkovBackend, MarkovBackendName, MarkovifyBackend
from .model import MarkovModel
from .tokenizer import MarkovTokenizer


class MarkovGenerator:
    """Generate Markov text through a selectable backend."""

    def __init__(
        self,
        model: MarkovModel,
        tokenizer: MarkovTokenizer | None = None,
        *,
        backend: MarkovBackendName = 'markovify',
    ) -> None:
        self.model = model
        self.tokenizer = tokenizer or MarkovTokenizer()

        if backend == 'markovify':
            self.backend = MarkovifyBackend(
                model,
                self.tokenizer,
            )
        else:
            self.backend = CustomMarkovBackend(
                model,
                self.tokenizer,
            )

    @property
    def backend_name(self) -> MarkovBackendName:
        """Return the active generation backend name."""
        if isinstance(self.backend, MarkovifyBackend):
            return 'markovify'
        return 'custom'

    def generate_tokens(
        self,
        *,
        max_tokens: int = 50,
        seed: str | None = None,
    ) -> list[str]:
        return self.backend.generate_tokens(
            max_tokens=max_tokens,
            seed=seed,
        )

    def generate(
        self,
        *,
        max_tokens: int = 50,
        seed: str | None = None,
    ) -> str:
        tokens = self.generate_tokens(
            max_tokens=max_tokens,
            seed=seed,
        )
        return self.tokenizer.detokenize(tokens)
