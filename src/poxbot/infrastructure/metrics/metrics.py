from typing import Any

from opentelemetry.metrics import Meter
from opentelemetry.trace import Tracer
from prometheus_client import start_http_server

from ...config.schema import TraceConfig
from .counters import CounterRegistry
from .gauges import GaugeProxy, GaugeRegistry
from .tracing import Tracing


class Metrics:
    def __init__(self, config: TraceConfig, tracer: Tracer, meter: Meter):
        self.config = config
        self.tracer = tracer
        self.meter = meter

        self.tracing = Tracing(tracer)
        self._counter_registry = CounterRegistry(meter)
        self._gauge_registry = GaugeRegistry(meter)

        self._dynamic_histograms = {}

    def span(self, *args, **kwargs):
        return self.tracing.span(*args, **kwargs)

    def span_async(self, *args, **kwargs):
        return self.tracing.span_async(*args, **kwargs)

    def increment_counter(
        self,
        name: str,
        description: str,
        amount: int | float = 1,
        labels: dict[str, Any] | None = None,
    ) -> None:
        c = self._counter_registry.counter(name, description)
        if labels:
            c.labels(**labels).inc(amount)
        else:
            c.inc(amount)

    def set_gauge(
        self,
        name: str,
        description: str,
        value: int | float,
        labels: dict[str, Any] | None = None,
    ) -> None:
        self._gauge_registry.set(name, float(value), description, labels)

    def gauge(self, name: str, description: str = '') -> GaugeProxy:
        return self._gauge_registry.gauge(name, description)

    def record_histogram(
        self,
        name: str,
        description: str,
        value: float,
        labels: dict[str, Any] | None = None,
        unit: str = 's',
    ) -> None:
        if name not in self._dynamic_histograms:
            self._dynamic_histograms[name] = self.meter.create_histogram(
                name,
                description=description,
                unit=unit,
            )
        self._dynamic_histograms[name].record(value, labels or {})

    def start_server(self):
        start_http_server(
            addr=self.config.prometheus_host,
            port=self.config.prometheus_server_port,
        )
