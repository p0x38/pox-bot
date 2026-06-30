from types import MappingProxyType
from typing import Any

from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from prometheus_client import start_http_server

from src.config.schema import TraceConfig
from src.logger_factory.logger import setup_logger

logger = setup_logger(__name__, "OpenTelemetryMetrics")


class OTelCounterProxy:
    def __init__(
        self,
        meter: metrics.Meter,
        name: str,
        description: str,
        label_cache: dict[frozenset[tuple], "OTelCounterProxy"] | None = None,
    ):
        self.meter = meter
        self.name = name
        self.description = description
        self.real_counter = self.meter.create_counter(name, description=description)
        self._current_attributes: dict[str, Any] | MappingProxyType[str, Any] = {}
        self._label_cache = label_cache if label_cache is not None else {}

    def labels(self, **kwargs: Any) -> "OTelCounterProxy":
        logger.debug(".labels(kwargs=%s)", kwargs)
        key = frozenset(kwargs.items())
        if key in self._label_cache:
            return self._label_cache[key]

        proxy = OTelCounterProxy(self.meter, self.name, self.description, label_cache=self._label_cache)
        proxy.real_counter = self.real_counter
        proxy._current_attributes = MappingProxyType(dict(kwargs))
        self._label_cache[key] = proxy
        return proxy

    def inc(self, amount: int | float = 1) -> None:
        logger.debug(".inc(amount=%d)", amount)
        self.real_counter.add(amount, dict(self._current_attributes))

    def add(self, amount: int | float, attributes: dict[str, Any] | None = None) -> None:
        logger.debug(".add(amount=%d, attributes=%s)", amount, str(attributes))
        self.real_counter.add(amount, dict(attributes or {}))


class OTelGaugeProxy:
    def __init__(self, manager: "Metrics", name: str, description: str):
        self.manager = manager
        self.name = name
        self.description = description
        self._current_attributes: dict[str, Any] = {}

    def labels(self, **kwargs: Any) -> "OTelGaugeProxy":
        proxy = OTelGaugeProxy(self.manager, self.name, self.description)
        proxy._current_attributes = kwargs
        return proxy

    def set(self, value: int | float) -> None:
        self.manager.set_gauge(self.name, self.description, value, self._current_attributes)


class Metrics:
    def __init__(self, config: TraceConfig):
        self.config = config
        resource = Resource(
            attributes={
                "service.name": "pox-discord-bot",
                "service.instance.id": "p0x38-discord.py-bot-2026",
            }
        )
        metric_exporter = OTLPMetricExporter(endpoint=config.opentelemetry_endpoint, insecure=config.insecure)
        metric_reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=config.export_interval_ms)

        prometheus_reader = PrometheusMetricReader()
        provider = MeterProvider(resource=resource, metric_readers=[metric_reader, prometheus_reader])
        metrics.set_meter_provider(provider)

        self.meter = metrics.get_meter("pox-discord-bot-metrics")

        self._dynamic_counters = {}
        self._dynamic_gauges = {}
        self._gauge_values = {}
        self._dynamic_histograms = {}

    def start_server(self):
        start_http_server(port=self.config.prometheus_server_port)

    def increment_counter(self, name: str, description: str, amount: int | float = 1, labels: dict[str, str] | None = None):
        if name not in self._dynamic_counters:
            self._dynamic_counters[name] = OTelCounterProxy(self.meter, name, description)

        if labels:
            self._dynamic_counters[name].labels(**labels).inc(amount)
        else:
            self._dynamic_counters[name].inc(amount)

    def set_gauge(self, name: str, description: str, value: int | float, labels: dict[str, str] | None = None):
        attributes_key = frozenset(labels.items()) if labels else frozenset()
        self._gauge_values[(name, attributes_key)] = (value, labels or {})

        if name not in self._dynamic_gauges:

            def create_fallback(gauge_name=name):
                def callback(options: Any) -> list[metrics.Observation]:  # noqa: ARG001
                    return [
                        metrics.Observation(val, attrs)
                        for (g_name, _), (val, attrs) in self._gauge_values.items()
                        if g_name == gauge_name
                    ]

                return callback

            self._dynamic_gauges[name] = self.meter.create_observable_gauge(
                name, description=description, callbacks=[create_fallback()]
            )

    def gauge(self, name: str, description: str = "") -> OTelGaugeProxy:
        return OTelGaugeProxy(self, name, description)

    def record_histogram(
        self, name: str, description: str, value: float, labels: dict[str, str] | None = None, unit: str = "s"
    ):
        if name not in self._dynamic_histograms:
            self._dynamic_histograms[name] = self.meter.create_histogram(name, description=description, unit=unit)

        self._dynamic_histograms[name].record(value, labels or {})
