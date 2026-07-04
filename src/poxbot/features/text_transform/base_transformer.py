from abc import ABC, abstractmethod
from collections.abc import Mapping
from time import perf_counter
from typing import Any, TypeVar

import numpy as np

from .models import (
    TransformerContext,
    TransformerMetrics,
    TransformerRequest,
    TransformerResult,
)


class BaseTextTransformer(ABC):
    """Abstract base class representing a unified Text Transformer.

    Every text transformers must inherit from this class.
    """

    def __init__(self, seed: int | None = None) -> None:
        self.rng = np.random.default_rng(seed)

    def apply_case_mask(self, text: str, mask: np.ndarray) -> str:
        chars = np.array(list(text), dtype='U1')
        upper = np.char.upper(chars)
        lower = np.char.lower(chars)
        return ''.join(np.where(mask, upper, lower))

    def transform(
        self,
        request: TransformerRequest,
        *,
        context: TransformerContext | None = None,
    ) -> TransformerResult:
        """The abstruct method to transform text."""
        started = perf_counter()
        output = self._transform(request, context=context)
        finished = perf_counter()

        return TransformerResult(
            transformer=self.name,
            output=output,
            input_length=len(request.text),
            metrics=TransformerMetrics(
                started_at=started,
                finished_at=finished,
                elapsed_ms=(finished - started) * 1000,
            ),
        )

    @abstractmethod
    def _transform(
        self,
        request: TransformerRequest,
        *,
        context: TransformerContext | None = None,
    ) -> str: ...

    @property
    def name(self) -> str:
        return self.__class__.__name__.removesuffix('Transformer').lower()
    
    @staticmethod
    def option(options: Mapping[str, Any], key: str, typ: type, default: Any) -> Any:
        value = options.get(key, default)
        
        if typ is bool:
            return bool(value)
        if typ is int:
            return int(value)
        if typ is float:
            return float(value)
        if typ is np.ndarray:
            return np.asarray(value)
        if not isinstance(value, typ):
            raise TypeError(  # noqa: TRY003
                f"{key!r} must be {typ.__name__}",
            )
        return value
    
    @classmethod
    def parse_options(cls, **options) -> dict[str, Any]:
        return options
    