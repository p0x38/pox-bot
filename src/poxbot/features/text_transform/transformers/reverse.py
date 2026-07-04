from __future__ import annotations

from ..base import ascii_to_ndarray, ndarray_to_ascii
from ..base_transformer import BaseTextTransformer
from ..constants import DECODE_LOOKUP, ENCODE_LOOKUP
from ..models import TransformerContext, TransformerRequest


class ReverseLetterTransformer(BaseTextTransformer):
    """Mirror alphanumeric characters."""

    def _transform(
        self,
        request: TransformerRequest,
        *,
        context: TransformerContext | None = None,
    ) -> str:
        """Mirror alphabet letters (A->Z, B->Y) via cached matrix arrays."""
        text = request.text
        if not text:
            return ''

        options = getattr(request, 'options', None) or {}
        mode = self.option(
            options,
            'type',
            str,
            'words',
        )
        if mode not in ('words', 'letters', 'both'):
            mode = 'words'

        current_text = text

        def mirror(t: str) -> str:
            lookup = (
                DECODE_LOOKUP if getattr(request, 'decode', False) else ENCODE_LOOKUP
            )
            matrix = ascii_to_ndarray(t)
            mapped = lookup[matrix]
            return ndarray_to_ascii(mapped)

        def reverse_words(t: str) -> str:
            return ' '.join(word[::-1] for word in t.split())

        if mode == 'letters':
            current_text = mirror(current_text)
        elif mode == 'words':
            current_text = reverse_words(current_text)
        elif mode == 'both':
            current_text = reverse_words(mirror(current_text))

        return current_text
