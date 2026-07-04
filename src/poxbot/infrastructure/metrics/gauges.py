from __future__ import annotations

from typing import Any

from opentelemetry import metrics


class GaugeRegistry:
    def __init__(self, meter: metrics.Meter):
        self.meter = meter
        self._values: dict[
            tuple[str, frozenset[tuple[str, Any]]],
            tuple[float, dict[str, Any]],
        ] = {}
        self._registered: dict[str, bool] = {}

    def set(
        self,
        name: str,
        value: float,
        description: str = '',
        labels: dict[str, Any] | None = None,
    ) -> None:
        labels = labels or {}
        key = (name, frozenset(labels.items()))
        self._values[key] = (value, labels)

        if name not in self._registered:
            self._register(name, description)

    def gauge(self, name: str, description: str = '') -> GaugeProxy:
        return GaugeProxy(self, name, description)

    def _register(self, name: str, description: str) -> None:
        self._registered[name] = True

        def callback(_options: Any):
            results = []
            for (g_name, _), (value, attrs) in self._values.items():
                if g_name == name:
                    results.append(metrics.Observation(value, attrs))
            return results

        self.meter.create_observable_gauge(
            name,
            callbacks=[callback],
            description=description,
        )


class GaugeProxy:
    def __init__(self, registry: GaugeRegistry, name: str, description: str):
        self.registry = registry
        self.name = name
        self.description = description
        self._labels: dict[str, Any] = {}

    def labels(self, **kwargs: Any) -> GaugeProxy:
        self._labels.update(kwargs)
        return self

    def set(self, value: float) -> None:
        self.registry.set(
            self.name,
            value,
            description=self.description,
            labels=self._labels,
        )
