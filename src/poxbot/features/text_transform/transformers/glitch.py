from __future__ import annotations

import numpy as np

from ....shared.exceptions.text_transform import InvalidGlitchRateError
from ..base_transformer import BaseTextTransformer
from ..models import TransformerContext, TransformerRequest


class GlitchVoidCaseTransformer(BaseTextTransformer):
    """Randomly inject void elements and blocky void characters."""

    def _transform(
        self, request: TransformerRequest, *, context: TransformerContext | None = None,
    ) -> str:
        """Replace 25% of the text characters with blocky glitch symbols."""
        text = request.text
        options = request.options
        if not text:
            return ''

        try:
            rate = float(options.get('rate', 0.25))
        except (ValueError, TypeError) as e:
            raise InvalidGlitchRateError() from e

        if not (0.0 <= rate <= 1.0):
            raise InvalidGlitchRateError()

        chars = np.array(list(text), dtype='U1')
        glitch_chars = np.array(['▰', '⚙', '', '█', '░', '▒', '⚔'], dtype='U1')

        glitch_mask = self.rng.random(len(chars)) < rate
        if np.any(glitch_mask):
            chars[glitch_mask] = self.rng.choice(glitch_chars, size=np.sum(glitch_mask))
        return ''.join(chars)
