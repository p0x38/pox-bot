from __future__ import annotations

import unicodedata

import numpy as np

from ..base_transformer import BaseTextTransformer
from ..models import TransformerContext, TransformerRequest


class ZalgoTransformer(BaseTextTransformer):
    """Corrupt text with combining unicode chaotic glitches.

    Appends multiple random combining Unicode characters to each grapheme,
    creating a corrupted, leaking "void" or "glitch" visual effect.
    """

    def _transform(
        self,
        request: TransformerRequest,
        *,
        context: TransformerContext | None = None,
    ) -> str:
        """Apply chaotic Zalgo corruption to the input text payload."""
        text = request.text
        if not text:
            return ''

        if getattr(request, 'decode', False):
            return self._unzalgo(text)
        return self._zalgo(text)

    def _zalgo(self, text: str) -> str:
        combining_chars = np.array(
            ['\u0305', '\u0332', '\u0338', '\u0320', '\u0311', '\u033f'],
            dtype='U1',
        )

        counts = self.rng.integers(2, 6, size=len(text))
        total_combining = np.sum(counts)
        random_combining = self.rng.choice(combining_chars, size=total_combining)
        splits = np.split(random_combining, np.cumsum(counts)[:-1])

        result = []
        for char, comb in zip(text, splits, strict=True):
            result.append(char)
            result.append(''.join(comb))
        return ''.join(result)

    def _unzalgo(self, text: str) -> str:
        return ''.join(c for c in text if unicodedata.category(c) != 'Mn')
