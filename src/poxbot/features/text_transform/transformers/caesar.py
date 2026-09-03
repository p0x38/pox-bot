from __future__ import annotations

import numpy as np

from ....shared.exceptions.text_transform import InvalidCaesarShiftError
from ..base import ascii_to_ndarray, ndarray_to_ascii
from ..base_transformer import BaseTextTransformer
from ..constants import ALPHA_ARR, ALPHA_STR
from ..models import TransformerContext, TransformerRequest


class CaesarCipherTransformer(BaseTextTransformer):
    """Classic Caesar cipher."""

    def _transform(
        self,
        request: TransformerRequest,
        *,
        context: TransformerContext | None = None,
    ) -> str:
        """Shift alphabet characters by a fixed key amount."""
        text = request.text
        options = request.options
        if not text:
            return ''

        try:
            shift = int(options.get('shift', 3))
        except (ValueError, TypeError) as e:
            raise InvalidCaesarShiftError() from e

        if shift == 0:
            raise InvalidCaesarShiftError()

        actual_shift = (-shift if request.decode else shift) % len(ALPHA_STR)

        lookup = np.arange(256, dtype=np.uint8)
        lookup[ALPHA_ARR] = np.roll(ALPHA_ARR, -actual_shift)

        return ndarray_to_ascii(lookup[ascii_to_ndarray(text)])
