import numpy as np

from ....shared.exceptions.text_transform import InvalidMockingTypeError
from ..base_transformer import BaseTextTransformer
from ..models import TransformerContext, TransformerRequest


class MockingCaseTransformer(BaseTextTransformer):
    """Sequentially or randomly alternate characters between upper and lowercase.

    Generates a mocking, sarcastic, or chaotic text effect (e.g., "mOcKiNg cAsE").
    Supports pure randomness, smooth text sequences, or dense aggression spans
    via customizable parameters.
    """

    def _transform(
        self,
        request: TransformerRequest,
        *,
        context: TransformerContext | None = None,
    ) -> str:
        """Apply mocking casing based on selected sequence type or random span."""
        text = request.text
        options = request.options
        if not text:
            return ''

        mode = options.get('type', 'random')
        chars = np.array(list(text), dtype='U1')
        upper_chars = np.char.upper(chars)
        lower_chars = np.char.lower(chars)

        if isinstance(mode, list | np.ndarray):
            pattern = np.asarray(mode, dtype=bool)
            if pattern.size > 0:
                reps = int(np.ceil(len(chars) / pattern.size))
                mask = np.tile(pattern, reps)[: len(chars)]
            else:
                mask = self.rng.choice([True, False], size=len(chars))
        elif isinstance(mode, str) and mode.lower() == 'random':
            mask = self.rng.choice([True, False], size=len(chars))
        elif isinstance(mode, str) and mode.lower() in ('sequence', 'alternate'):
            mask = np.arange(len(chars)) % 2 == 0
        else:
            try:
                span = int(mode)
            except (ValueError, TypeError) as e:
                raise InvalidMockingTypeError(mode) from e

            if span <= 0:
                raise InvalidMockingTypeError(mode)

            mask = (np.arange(len(chars)) // span) % 2 == 0

        return ''.join(np.where(mask, upper_chars, lower_chars))
