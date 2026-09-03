from __future__ import annotations

import numpy as np

from ....shared.exceptions.text_transform import InvalidRailFenceKeyError
from ..base import ascii_to_ndarray, ndarray_to_ascii
from ..base_transformer import BaseTextTransformer
from ..models import TransformerContext, TransformerRequest


class RailFenceTransformer(BaseTextTransformer):
    """Rail fence cipher."""

    def _transform(
        self,
        request: TransformerRequest,
        *,
        context: TransformerContext | None = None,
    ) -> str:
        """Route letters in a zigzag pattern across virtual rails."""
        text = request.text
        options = request.options
        try:
            key = int(options.get('key', 2))
        except (ValueError, TypeError) as e:
            raise InvalidRailFenceKeyError() from e

        if key <= 1:
            raise InvalidRailFenceKeyError()

        length = len(text)

        if key <= 1 or length == 0:
            return text

        cycle = 2 * (key - 1)

        pattern = np.arange(length) % cycle
        pattern = np.where(pattern < key, pattern, cycle - pattern)

        indices = np.argsort(pattern, kind='stable')
        data = ascii_to_ndarray(text)

        if request.decode:
            output = np.empty(length, dtype=np.uint8)
            output[indices] = data
            return ndarray_to_ascii(output)

        return ndarray_to_ascii(data[indices])
