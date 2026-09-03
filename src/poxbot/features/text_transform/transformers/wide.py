from __future__ import annotations

import numpy as np

from ..base_transformer import BaseTextTransformer
from ..models import TransformerContext, TransformerRequest


class WideCaseTransformer(BaseTextTransformer):
    """Spacify and upper-case text.

    Transforms the input string into all uppercase and inserts spaces between
    every character, while safely deduplicating existing whitespace. Does not
    require `self.rng`, but inherits it safely from the base class.
    """

    def _transform(
        self,
        request: TransformerRequest,
        *,
        context: TransformerContext | None = None,
    ) -> str:
        """Filter whitespace -> uppercase -> separate characters by spaces."""
        text = request.text
        if not text:
            return ''
        chars = np.array(list(text), dtype='U1')
        mask = chars != ' '
        return ' '.join(np.char.upper(chars[mask]))
