from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any


@dataclass(slots=True, frozen=True)
class TransformerRequest:
    text: str
    decode: bool = False
    options: Mapping[str, Any] = field(
        default_factory=lambda: MappingProxyType({}),
    )


@dataclass(slots=True, frozen=True)
class TransformerResult:
    transformer: str
    output: str
    metrics: TransformerMetrics
    success: bool = True
    input_length: int = 0
    metadata: Mapping[str, Any] = field(
        default_factory=lambda: MappingProxyType({}),
    )
    diagnostics: tuple[str, ...] = ()

    @property
    def output_length(self) -> int:
        return len(self.output)


@dataclass(slots=True)
class TransformerContext:
    locale: str | None = None
    request_id: str | None = None
    trace_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TransformerMetrics:
    started_at: float
    finished_at: float
    elapsed_ms: float
