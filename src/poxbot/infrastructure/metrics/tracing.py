from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager
from typing import Any

from opentelemetry.trace import Span, Tracer


class Tracing:
    def __init__(self, tracer: Tracer):
        self.tracer = tracer

    @contextmanager
    def span(self, name: str, **attributes: Any) -> Generator[Span, None, None]:
        with self.tracer.start_as_current_span(name) as span:
            for key, value in attributes.items():
                span.set_attribute(key, value)
            yield span

    @asynccontextmanager
    async def span_async(
        self,
        name: str,
        **attributes: Any,
    ) -> AsyncGenerator[Span, None]:
        with self.tracer.start_as_current_span(name) as span:
            for key, value in attributes.items():
                span.set_attribute(key, value)
            yield span
