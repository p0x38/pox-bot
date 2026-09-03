import inspect
from collections.abc import Callable
from typing import ClassVar

from ....dsl import SafeStringPredicateEvaluator
from ..base_transformer import BaseTextTransformer
from ..models import TransformerContext, TransformerRequest


class PredicateCaseTransformer(BaseTextTransformer):
    """Modulate character casing based on a dynamic user-defined predicate function.

    Evaluates each character node against a given condition vector, rendering
    elements as uppercase when the criteria is satisfied.
    """

    _sig_cache: ClassVar[dict[Callable[..., object], int]] = {}

    @staticmethod
    def _mirror_char(char: str) -> str:
        if not char.isalpha() or len(char) != 1:
            return char

        o = ord(char)

        if 65 <= o <= 90:
            return chr(90 - (o - 65))
        if 97 <= o <= 122:
            return chr(122 - (o - 97))
        return char

    def _transform(
        self,
        request: TransformerRequest,
        *,
        context: TransformerContext | None = None,
    ) -> str:
        """Evaluate string payload elements via functional callable filter."""
        text = request.text
        options = request.options or {}
        if not text:
            return ''

        predicate = options.get('predicate')

        if isinstance(predicate, str) and predicate.strip():
            evaluator = SafeStringPredicateEvaluator(predicate)
            actions = [
                evaluator.evaluate(char, idx, text) for idx, char in enumerate(text)
            ]

            if evaluator.error_message:
                return f'[DSL Error] {evaluator.error_message}'
        elif callable(predicate):
            cached = self._sig_cache.get(predicate)

            if cached is None:
                try:
                    cached = len(inspect.signature(predicate).parameters)
                except (ValueError, TypeError, AttributeError):
                    cached = 1
                self._sig_cache[predicate] = cached

            param_count = cached

            try:
                if param_count >= 2:
                    raw = [predicate(char, idx) for idx, char in enumerate(text)]
                else:
                    raw = [predicate(char) for char in text]
            except Exception:
                return text.lower()

            actions = []
            for r in raw:
                if isinstance(r, bool):
                    actions.append('upper' if r else 'lower')
                elif isinstance(r, str):
                    if r in {
                        'upper',
                        'lower',
                        'delete',
                        'reverse',
                        'keep',
                    }:
                        actions.append(r)
                    else:
                        actions.append('keep')
                else:
                    actions.append('keep')
        else:
            return text.lower()

        result_chars = []
        for idx, char in enumerate(text):
            act = 'keep' if idx >= len(actions) else actions[idx]

            if act == 'upper':
                result_chars.append(char.upper())
            elif act == 'lower':
                result_chars.append(char.lower())
            elif act == 'delete':
                continue
            elif act == 'reverse':
                result_chars.append(self._mirror_char(char))
            elif act == 'keep':
                result_chars.append(char)
            else:
                result_chars.append(act)
        return ''.join(result_chars)
