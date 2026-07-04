from __future__ import annotations

import numpy as np

from ....shared.exceptions.text_transform import InvalidBlockSizeError
from ..base import ascii_to_ndarray, ndarray_to_ascii
from ..base_transformer import BaseTextTransformer
from ..models import TransformerContext, TransformerRequest


class Psc1Transformer(BaseTextTransformer):
    """Apply ROT13 and reverse every 5-character block."""

    def _transform(
        self, request: TransformerRequest, *, context: TransformerContext | None = None,
    ) -> str:
        """Run ROT13 rotation and invert elements within chunk boundaries."""
        text = request.text
        options = request.options

        if not text:
            return ''

        try:
            chunk_size = int(options.get('chunk_size', 5))
        except (ValueError, TypeError) as e:
            raise InvalidBlockSizeError() from e

        if chunk_size < 1:
            raise InvalidBlockSizeError()

        data = ascii_to_ndarray(text).copy()

        def rot13(values: np.ndarray) -> np.ndarray:
            transformed = values.copy()
            upper = (transformed >= 65) & (transformed <= 90)
            lower = (transformed >= 97) & (transformed <= 122)
            transformed[upper] = (transformed[upper] - 65 + 13) % 26 + 65
            transformed[lower] = (transformed[lower] - 97 + 13) % 26 + 97
            return transformed

        def reverse_chunks(values: np.ndarray) -> np.ndarray:
            chunks = [
                values[index : index + chunk_size][::-1]
                for index in range(0, len(values), chunk_size)
            ]
            return np.concatenate(chunks) if chunks else values

        if request.decode:
            data = reverse_chunks(data)
            data = rot13(data)
        else:
            data = rot13(data)
            data = reverse_chunks(data)

        return ndarray_to_ascii(data)
