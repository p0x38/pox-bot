from __future__ import annotations

import importlib
import inspect
import pkgutil
from contextlib import nullcontext
from typing import TYPE_CHECKING

from ...shared.exceptions.text_transform import NoTextTransformerObjectError
from ..text_transform import transformers
from .base_transformer import BaseTextTransformer
from .models import TransformerContext, TransformerRequest, TransformerResult

if TYPE_CHECKING:
    from ...shared.utils.metrics import Metrics


class TextTransformManager:
    """Manager responsible for lifecycle, routing, and telemetry of text transformers.

    Dynamically discovers and registers all valid text transformer classes
    within the `transformers` package. Handles pipeline execution and
    exports continuous performance metrics (durations, character throughput,
    invocation counts) via the configured metrics service proxy.
    """

    def __init__(self, metrics: Metrics | None = None, seed: int | None = None):
        """Initialize manager and automatically register discoverable components.

        Args:
            metrics (Metrics | None): Optional telemetry proxy to record metrics.
            seed (int | None): Optional pseudo-random seed for individual
                transformers.
        """
        self._transformers: dict[str, BaseTextTransformer] = {}
        self.seed = seed
        self.metrics_service = metrics

        self.register_transformers()

    def list_transformers(self) -> list[str]:
        """Retrieve a sorted list of all currently registered transformer names.

        Useful for application command autocomplete choices and dynamic
        Pydantic validation schema generation.

        Returns:
            list[str]: A sorted list of unique registered identifier keys.
        """
        return sorted(self._transformers.keys())

    def register_transformer(self, name: str, transformer: BaseTextTransformer) -> None:
        """Explicitly register a transformer instance under a unique identifier.

        Args:
            name (str): The identifier key (usually matching the filename).
            transformer (BaseTextTransformer): Instantiated transformer strategy.
        """
        self._transformers[name] = transformer

    def register_transformers(self):
        """Scan package space to dynamically load and register eligible strategies.

        Iterates through all submodules, looking for non-abstract subclasses of
        `BaseTextTransformer` while ignoring the base class itself. Instantiates
        each valid target with the configured manager seed.
        """
        for _, m_name, _ in pkgutil.iter_modules(transformers.__path__):
            full_m_name = f'{transformers.__name__}.{m_name}'
            module = importlib.import_module(full_m_name)

            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    inspect.isclass(attr)
                    and issubclass(attr, BaseTextTransformer)
                    and attr is not BaseTextTransformer
                    and not inspect.isabstract(attr)
                ):
                    self.register_transformer(m_name, attr(seed=self.seed))

    def create_request(
        self,
        name: str,
        text: str,
        *,
        decode: bool = False,
        **options,
    ) -> TransformerRequest:
        transformer = self.get_transformer(name)

        return TransformerRequest(
            text=text,
            decode=decode,
            options=transformer.parse_options(**options),
        )

    def transform(
        self,
        name: str,
        request: TransformerRequest,
        *,
        context: TransformerContext | None = None,
    ) -> TransformerResult:
        """Execute a text transformation strategy while capturing runtime metrics."""
        if name not in self._transformers:
            raise NoTextTransformerObjectError(name)

        labels = {'transformer_name': name}

        span_ctx = (
            self.metrics_service.span(
                f'bot_text_transformer_transform:{name}',
                **labels,
            )
            if self.metrics_service
            else nullcontext()
        )

        with span_ctx as span:
            if hasattr(span, 'set_attribute'):
                span.set_attribute('text.chars_in', len(request.text))  # pyright: ignore[reportOptionalMemberAccess]

            request = self.create_request(
                name,
                request.text,
                decode=request.decode,
                **request.options,
            )
            result = self._transformers[name].transform(request, context=context)

            if hasattr(span, 'set_attribute'):
                span.set_attribute('text.chars_out', result.output_length)  # pyright: ignore[reportOptionalMemberAccess]
                span.set_attribute('transformer.duration_ms', result.metrics.elapsed_ms)  # pyright: ignore[reportOptionalMemberAccess]

            if self.metrics_service:
                self.metrics_service.increment_counter(
                    'bot_text_transformer_usage_total',
                    description='Total number of times a text transformer was invoked',
                    labels=labels,
                )
                self.metrics_service.record_histogram(
                    'bot_text_transformer_execution_duration_ms',
                    description='Transformer execution duration in ms',
                    value=result.metrics.elapsed_ms,
                    labels=labels,
                    unit='ms',
                )
                self.metrics_service.increment_counter(
                    'bot_text_transformer_processed_chars_total',
                    description='Total number of characters processed',
                    amount=result.input_length,
                    labels={'direction': 'in', **labels},
                )
                self.metrics_service.increment_counter(
                    'bot_text_transformer_processed_chars_total',
                    description='Total number of characters processed',
                    amount=result.output_length,
                    labels={'direction': 'out', **labels},
                )

            return result

    def pipeline(
        self,
        request: TransformerRequest,
        steps: list[tuple[str, dict]],
        *,
        context: TransformerContext | None = None,
    ) -> TransformerResult:
        """Sequentially execute a chain of multiple text transformations."""
        pipe_ctx = (
            self.metrics_service.span(
                'bot_text_pipeline_execution',
                steps_count=len(steps),
            )
            if self.metrics_service
            else nullcontext()
        )

        if not steps:
            raise ValueError('Pipeline must contain at least one transformer.')

        with pipe_ctx:
            first_name, first_options = steps[0]

            result = self.transform(
                first_name,
                TransformerRequest(
                    text=request.text,
                    decode=request.decode,
                    options=first_options,
                ),
                context=context,
            )

            for name, options in steps[1:]:
                result = self.transform(
                    name,
                    TransformerRequest(
                        text=result.output,
                        decode=request.decode,
                        options=options,
                    ),
                    context=context,
                )

            return result

    def get_transformer(self, name: str) -> BaseTextTransformer:
        if name not in self._transformers:
            raise NoTextTransformerObjectError(name)

        return self._transformers[name]
