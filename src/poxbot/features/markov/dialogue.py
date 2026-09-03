from __future__ import annotations

import re
from dataclasses import dataclass

from ..chatbot.tfidf import TfidfIndex
from .tokenizer import MarkovTokenizer


@dataclass(slots=True)
class DialoguePair:
    """A learned user message and the response associated with it."""

    prompt: str
    response: str


@dataclass(frozen=True, slots=True)
class DialogueMatch:
    """A retrieved dialogue response and its similarity score."""

    response: str
    score: float


class MarkovDialogueMemory:
    """Lightweight conversational retrieval using TF-IDF and cosine similarity."""

    _whitespace = re.compile(r'\s+')

    def __init__(
        self,
        tokenizer: MarkovTokenizer | None = None,
        *,
        max_entries: int = 5000,
    ) -> None:
        self.tokenizer = tokenizer or MarkovTokenizer()
        self.max_entries = max_entries
        self.entries: list[DialoguePair] = []
        self._index = TfidfIndex()
        self._index_dirty = True

    @staticmethod
    def _normalize(text: str) -> str:
        text = text.casefold().strip()
        return MarkovDialogueMemory._whitespace.sub(' ', text)

    def _tokens(self, text: str) -> tuple[str, ...]:
        return tuple(
            token
            for token in self.tokenizer.tokenize(self._normalize(text))
            if token.strip()
        )

    def _rebuild_index(self) -> None:
        if not self._index_dirty:
            return

        self._index.fit(self._tokens(entry.prompt) for entry in self.entries)
        self._index_dirty = False

    def learn(self, prompt: str, response: str) -> None:
        """Learn a dialogue pair."""
        prompt = prompt.strip()
        response = response.strip()

        if not prompt or not response:
            return

        for entry in self.entries:
            if entry.prompt == prompt and entry.response == response:
                return

        self.entries.append(
            DialoguePair(
                prompt=prompt,
                response=response,
            ),
        )

        if len(self.entries) > self.max_entries:
            del self.entries[: len(self.entries) - self.max_entries]

        self._index_dirty = True

    def find_match(
        self,
        query: str,
        *,
        threshold: float = 0.55,
    ) -> DialogueMatch | None:
        """Find the best learned response and its cosine similarity score."""
        query = query.strip()

        if not query or not self.entries:
            return None

        normalized_query = self._normalize(query)

        # Prefer exact matches regardless of the TF-IDF score.
        for entry in reversed(self.entries):
            if self._normalize(entry.prompt) == normalized_query:
                return DialogueMatch(entry.response, 1.0)

        self._rebuild_index()
        query_tokens = self._tokens(query)
        ranked = self._index.rank(query_tokens)

        for index, score in ranked:
            if score >= threshold:
                return DialogueMatch(self.entries[index].response, score)

        return None

    def similarity(self, query: str) -> float:
        """Return the highest learned-prompt similarity for a query."""
        match = self.find_match(query, threshold=0.0)
        return match.score if match is not None else 0.0

    def find(
        self,
        query: str,
        *,
        threshold: float = 0.55,
    ) -> str | None:
        """Find the best learned response for a query."""
        match = self.find_match(query, threshold=threshold)
        return match.response if match is not None else None

    def clear(self) -> None:
        """Clear all learned dialogue pairs."""
        self.entries.clear()
        self._index.clear()
        self._index_dirty = False
