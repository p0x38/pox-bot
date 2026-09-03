from __future__ import annotations

import re

import numpy as np

from ..base_transformer import BaseTextTransformer
from ..models import TransformerContext, TransformerRequest

_WORD_RE = re.compile(r'[A-Za-z]+')


class MeowTransformer(BaseTextTransformer):
    """Convert every word into a weighted meow."""

    _VARIANTS = np.array(
        [
            ('meow', ('m', 'e', 'o', 'w')),
            ('miaw', ('m', 'i', 'a', 'w')),
            ('maow', ('m', 'a', 'o', 'w')),
        ],
        dtype=object,
    )
    _WEIGHTS = np.array([50.0, 2.0, 1.0])
    _WEIGHTS /= _WEIGHTS.sum()

    def _transform(
        self, request: TransformerRequest, *, context: TransformerContext | None = None
    ) -> str:
        return _WORD_RE.sub(lambda match: self._meow_word(match.group()), request.text)

    def _meow_word(self, word: str) -> str:
        length = len(word)
        if length == 0:
            return ''

        mask = np.fromiter((c.isupper() for c in word), dtype=bool)

        variant_index = self.rng.choice(
            len(self._VARIANTS),
            p=self._WEIGHTS,
        )

        base_word, letters = self._VARIANTS[variant_index]

        if length == 3:
            return self.apply_case_mask('maw', mask)

        if length < 4:
            return self.apply_case_mask(base_word, mask)

        counts = np.full(4, length // 4, dtype=int)
        counts[1] += length % 4

        meow = ''.join(
            letter * int(count)
            for letter, count in zip(
                letters,
                counts,
                strict=True,
            )
        )

        return self.apply_case_mask(meow, mask)
