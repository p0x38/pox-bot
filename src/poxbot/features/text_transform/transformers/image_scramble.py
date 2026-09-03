from __future__ import annotations

import numpy as np

from ....shared.exceptions.text_transform import InvalidSeedKeyError
from ..base import ascii_to_ndarray
from ..base_transformer import BaseTextTransformer
from ..models import TransformerContext, TransformerRequest


class ImageGlitchScrambleTransformer(BaseTextTransformer):
    """Scramble text as though it were rows of pixels in a square image."""

    def _transform(
        self,
        request: TransformerRequest,
        *,
        context: TransformerContext | None = None,
    ) -> str:
        """Reshape string to a 2D matrix, shift rows randomly, and transpose."""
        text = request.text
        options = request.options

        length = len(text)
        if length < 4:
            return text

        try:
            seed_key = options.get('seed_key', 42)
        except (ValueError, TypeError) as e:
            raise InvalidSeedKeyError() from e

        side = int(np.floor(np.sqrt(length)))
        usable = side * side
        remainder = text[usable:]

        matrix = ascii_to_ndarray(text[:usable]).copy().reshape(side, side)

        rng = np.random.default_rng(seed_key)
        shifts = rng.integers(1, side, size=side)

        if request.decode:
            matrix = matrix.T
            for row, shift in enumerate(shifts):
                matrix[row] = np.roll(matrix[row], -shift)
        else:
            for row, shift in enumerate(shifts):
                matrix[row] = np.roll(matrix[row], shift)
            matrix = matrix.T

        return matrix.ravel().tobytes().decode('ascii') + remainder
