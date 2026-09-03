from __future__ import annotations

import textwrap

import numpy as np

from ....shared.exceptions.text_transform import (
    BinaryDecodeError,
    InvalidBlockSizeError,
)
from ..base import ascii_to_ndarray
from ..base_transformer import BaseTextTransformer
from ..models import TransformerContext, TransformerRequest


class BinaryTransformer(BaseTextTransformer):
    """Binary encoder and decoder using NumPy bits unpacking."""

    def _transform(
        self,
        request: TransformerRequest,
        *,
        context: TransformerContext | None = None,
    ) -> str:
        """Encode text to space-separated binary strings or decode them back."""
        text = request.text
        options = request.options

        if not text:
            return ''

        try:
            block_size = int(options.get('block_size', 8))
        except (ValueError, TypeError) as e:
            raise InvalidBlockSizeError() from e

        if block_size < 1:
            raise InvalidBlockSizeError()

        if request.decode:
            clean = ''.join(text.split())
            if not clean:
                return ''

            if any(c not in '01' for c in clean):
                raise BinaryDecodeError()

            clean = clean[: len(clean) - len(clean) % block_size]
            return ''.join(
                chr(int(bits, 2)) for bits in textwrap.wrap(clean, block_size)
            )

        bits = np.unpackbits(ascii_to_ndarray(text)).reshape(-1, block_size)
        return ' '.join(''.join(row.astype(str)) for row in bits)
