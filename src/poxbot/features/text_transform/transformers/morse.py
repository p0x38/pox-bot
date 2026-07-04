from __future__ import annotations

from ....shared.exceptions.text_transform import InvalidMorseTokenError
from ..base_transformer import BaseTextTransformer
from ..constants import MORSE_CODE_TABLE
from ..models import TransformerContext, TransformerRequest


class MorseCodeTransformer(BaseTextTransformer):
    """Encode or decode Morse code."""

    def _transform(
        self, request: TransformerRequest, *, context: TransformerContext | None = None,
    ) -> str:
        """Convert plaintext into slash-separated Morse code, or vice versa."""
        text = request.text
        options = request.options
        table = options.get('morse_table') or MORSE_CODE_TABLE
        w_sep = options.get('word_sep', '/')

        if not text:
            return ''

        if not request.decode:
            return ' '.join(
                filter(
                    None,
                    (table.get(c, w_sep if c == ' ' else '') for c in text),
                ),
            )

        reverse = {v: k for k, v in table.items()}
        result_chars = []

        for token in text.split():
            if token == w_sep:
                result_chars.append(' ')
                continue
            if token not in reverse:
                raise InvalidMorseTokenError(token)
            result_chars.append(reverse[token])

        return ''.join(result_chars)
