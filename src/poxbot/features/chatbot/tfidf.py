from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable


class TfidfIndex:
    """Small in-memory TF-IDF index for lightweight text retrieval."""

    def __init__(self) -> None:
        self._documents: list[tuple[str, ...]] = []
        self._document_frequency: Counter[str] = Counter()

    @property
    def document_count(self) -> int:
        """Return the number of indexed documents."""
        return len(self._documents)

    def clear(self) -> None:
        """Remove all indexed documents."""
        self._documents.clear()
        self._document_frequency.clear()

    def fit(self, documents: Iterable[Iterable[str]]) -> None:
        """Build the index from tokenized documents."""
        self.clear()

        for document in documents:
            tokens = tuple(token for token in document if token.strip())
            self._documents.append(tokens)
            self._document_frequency.update(set(tokens))

    def cosine_similarity(
        self,
        query: Iterable[str],
        document: Iterable[str],
    ) -> float:
        """Return cosine similarity between a query and a document."""
        query_tokens = tuple(token for token in query if token.strip())
        document_tokens = tuple(token for token in document if token.strip())

        if not query_tokens or not document_tokens:
            return 0.0

        corpus_size = max(self.document_count, 1)
        query_counts = Counter(query_tokens)
        document_counts = Counter(document_tokens)
        vocabulary = query_counts.keys() | document_counts.keys()

        query_norm = 0.0
        document_norm = 0.0
        dot_product = 0.0

        for token in vocabulary:
            document_frequency = self._document_frequency.get(token, 0)
            inverse_document_frequency = math.log(
                (1 + corpus_size) / (1 + document_frequency),
            ) + 1.0

            query_weight = query_counts[token] * inverse_document_frequency
            document_weight = document_counts[token] * inverse_document_frequency

            query_norm += query_weight * query_weight
            document_norm += document_weight * document_weight
            dot_product += query_weight * document_weight

        if query_norm == 0.0 or document_norm == 0.0:
            return 0.0

        return dot_product / math.sqrt(query_norm * document_norm)

    def rank(self, query: Iterable[str]) -> list[tuple[int, float]]:
        """Rank indexed documents by cosine similarity."""
        query_tokens = tuple(query)
        return sorted(
            (
                (index, self.cosine_similarity(query_tokens, document))
                for index, document in enumerate(self._documents)
            ),
            key=lambda item: item[1],
            reverse=True,
        )
