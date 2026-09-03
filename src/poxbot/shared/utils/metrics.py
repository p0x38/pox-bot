from __future__ import annotations

from collections.abc import Generator
from contextlib import asynccontextmanager, contextmanager
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBasedTraceIdRatio
from prometheus_client import start_http_server

if TYPE_CHECKING:
    from ...config.schema import TraceConfig


class OTelCounterProxy:
    def __init__(
        self,
        meter: metrics.Meter,
        name: str,
        description: str,
        label_cache: dict[frozenset[tuple[str, Any]], OTelCounterProxy] | None = None,
    ):
        self.meter = meter
        self.name = name
        self.description = description
        self.real_counter = self.meter.create_counter(name, description=description)
        self._current_attributes: dict[str, Any] | MappingProxyType[str, Any] = {}
        self._label_cache = label_cache if label_cache is not None else {}

    def labels(self, **kwargs: Any) -> OTelCounterProxy:
        key = frozenset(kwargs.items())
        if key in self._label_cache:
            return self._label_cache[key]

        proxy = OTelCounterProxy(
            self.meter,
            self.name,
            self.description,
            label_cache=self._label_cache,
        )
        proxy.real_counter = self.real_counter
        proxy._current_attributes = MappingProxyType(dict(kwargs))
        self._label_cache[key] = proxy
        return proxy

    def inc(self, amount: int | float = 1) -> None:
        self.real_counter.add(amount, dict(self._current_attributes))

    def add(
        self,
        amount: int | float,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        self.real_counter.add(amount, dict(attributes or {}))


class OTelGaugeProxy:
    def __init__(self, manager: Metrics, name: str, description: str):
        self.manager = manager
        self.name = name
        self.description = description
        self._current_attributes: dict[str, Any] = {}

    def labels(self, **kwargs: Any) -> OTelGaugeProxy:
        proxy = OTelGaugeProxy(self.manager, self.name, self.description)
        proxy._current_attributes = kwargs
        return proxy

    def set(self, value: int | float) -> None:
        self.manager.set_gauge(
            self.name,
            self.description,
            value,
            self._current_attributes,
        )


class Metrics:
    def __init__(self, config: TraceConfig):
        from ...infrastructure.logger import get_logger  # ruff: ignore[import-outside-top-level, unsorted-imports]

        self.logger = get_logger(__name__, prefix='TelemetryManager')
        self.config = config
        self.resource = Resource(
            attributes={
                'service.name': 'pox-discord-bot',
                'service.instance.id': 'p0x38-discord.py-bot-2026',
            },
        )

        sampler = ParentBasedTraceIdRatio(config.sampling_ratio)
        trace_provider = TracerProvider(resource=self.resource, sampler=sampler)

        trace_endpoint = config.otlp_traces_endpoint or config.opentelemetry_endpoint
        if trace_endpoint:
            if not trace_endpoint.startswith(('http://', 'https://')):
                trace_endpoint = f'http://{trace_endpoint}'

            trace_provider.add_span_processor(
                BatchSpanProcessor(
                    OTLPSpanExporter(
                        endpoint=trace_endpoint,
                        insecure=config.insecure,
                    ),
                    max_queue_size=config.max_batch_size * 4,
                    max_export_batch_size=config.max_batch_size,
                    schedule_delay_millis=config.export_interval_ms,
                ),
            )

        trace.set_tracer_provider(trace_provider)
        self.tracer = trace.get_tracer('pox-discord-bot-tracer')

        metric_readers = []
        metrics_endpoint = config.otlp_metrics_endpoint or config.opentelemetry_endpoint
        if metrics_endpoint:
            if not metrics_endpoint.startswith(('http://', 'https://')):
                metrics_endpoint = f'http://{metrics_endpoint}'

            metric_exporter = OTLPMetricExporter(
                endpoint=metrics_endpoint,
                insecure=config.insecure,
            )
            metric_readers.append(
                PeriodicExportingMetricReader(
                    metric_exporter,
                    export_interval_millis=config.export_interval_ms,
                ),
            )

        prometheus_reader = PrometheusMetricReader()
        metric_readers.append(prometheus_reader)

        provider = MeterProvider(resource=self.resource, metric_readers=metric_readers)
        metrics.set_meter_provider(provider)
        self.meter = metrics.get_meter('pox-discord-bot-metrics')

        self._dynamic_counters: dict[str, OTelCounterProxy] = {}
        self._dynamic_gauges: dict[str, Any] = {}
        self._gauge_values: dict[
            tuple[str, frozenset[tuple[str, Any]]],
            tuple[int | float, dict[str, Any]],
        ] = {}
        self._dynamic_histograms: dict[str, Any] = {}

    def start_server(self):
        if not self.config.otlp_traces_endpoint:
            start_http_server(
                addr=self.config.prometheus_host,
                port=self.config.prometheus_server_port,
            )

        self.logger.info(
            'Prometheus metrics endpoint listening on http://%s:%d',
            self.config.prometheus_host,
            self.config.prometheus_server_port,
        )

    def increment_counter(
        self,
        name: str,
        description: str,
        amount: int | float = 1,
        labels: dict[str, str] | None = None,
    ):
        if name not in self._dynamic_counters:
            self._dynamic_counters[name] = OTelCounterProxy(
                self.meter,
                name,
                description,
            )
        if labels:
            self._dynamic_counters[name].labels(**labels).inc(amount)
        else:
            self._dynamic_counters[name].inc(amount)

    def set_gauge(
        self,
        name: str,
        description: str,
        value: int | float,
        labels: dict[str, str] | None = None,
    ):
        attributes_key = frozenset(labels.items()) if labels else frozenset()
        self._gauge_values[name, attributes_key] = (value, labels or {})

        if name not in self._dynamic_gauges:

            def create_fallback(gauge_name=name):
                def callback(options: Any) -> list[metrics.Observation]:
                    return [
                        metrics.Observation(val, attrs)
                        for (g_name, _), (val, attrs) in self._gauge_values.items()
                        if g_name == gauge_name
                    ]

                return callback

            self._dynamic_gauges[name] = self.meter.create_observable_gauge(
                name,
                description=description,
                callbacks=[create_fallback()],
            )

    def gauge(self, name: str, description: str = '') -> OTelGaugeProxy:
        return OTelGaugeProxy(self, name, description)

    def record_histogram(
        self,
        name: str,
        description: str,
        value: float,
        labels: dict[str, str] | None = None,
        unit: str = 's',
    ):
        if name not in self._dynamic_histograms:
            self._dynamic_histograms[name] = self.meter.create_histogram(
                name,
                description=description,
                unit=unit,
            )
        self._dynamic_histograms[name].record(value, labels or {})

    @contextmanager
    def span(self, name: str, **attributes) -> Generator[Any, None, None]:
        with self.tracer.start_as_current_span(name) as span:
            for key, value in attributes.items():
                span.set_attribute(key, value)
            yield span

    @asynccontextmanager
    async def span_async(self, name: str, **attributes):
        with self.tracer.start_as_current_span(name) as span:
            for key, value in attributes.items():
                span.set_attribute(key, value)
            yield span
