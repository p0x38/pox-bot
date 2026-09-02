from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from .tokenizer import MarkovTokenizer


@dataclass(slots=True)
class DialoguePair:
    """A learned user message and the response associated with it."""

    prompt: str
    response: str


class MarkovDialogueMemory:
    """Lightweight conversational retrieval without an LLM or transformer.

    This is deliberately lexical rather than semantic: it combines token
    overlap with fuzzy string similarity to find previously learned replies.
    """

    _whitespace = re.compile(r"\s+")

    def __init__(
        self,
        tokenizer: MarkovTokenizer | None = None,
        *,
        max_entries: int = 5000,
    ) -> None:
        self.tokenizer = tokenizer or MarkovTokenizer()
        self.max_entries = max_entries
        self.entries: list[DialoguePair] = []

    @staticmethod
    def _normalize(text: str) -> str:
        text = text.lower().strip()
        return MarkovDialogueMemory._whitespace.sub(' ', text)

    def _tokens(self, text: str) -> set[str]:
        return {
            token
            for token in self.tokenizer.tokenize(self._normalize(text))
            if token.strip()
        }

    def learn(self, prompt: str, response: str) -> None:
        prompt = prompt.strip()
        response = response.strip()

        if not prompt or not response:
            return

        pair = DialoguePair(prompt=prompt, response=response)

        self.entries.append(pair)

        if len(self.entries) > self.max_entries:
            del self.entries[: len(self.entries) - self.max_entries]

    def _score(self, query: str, candidate: str) -> float:
        query_tokens = self._tokens(query)
        candidate_tokens = self._tokens(candidate)

        if not query_tokens or not candidate_tokens:
            return 0.0

        overlap = len(query_tokens & candidate_tokens) / len(
            query_tokens | candidate_tokens,
        )

        fuzzy = SequenceMatcher(
            None,
            self._normalize(query),
            self._normalize(candidate),
        ).ratio()

        return overlap * 0.7 + fuzzy * 0.3

    def find(self, query: str, *, threshold: float = 0.45) -> str | None:
        if not query.strip() or not self.entries:
            return None

        best_score = threshold
        best_response: str | None = None

        for entry in self.entries:
            score = self._score(query, entry.prompt)

            if score > best_score:
                best_score = score
                best_response = entry.response

        return best_response

    def clear(self) -> None:
        self.entries.clear()
