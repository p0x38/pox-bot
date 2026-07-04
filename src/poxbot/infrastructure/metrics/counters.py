from types import MappingProxyType
from typing import Any

from opentelemetry.metrics import Counter, Meter


class CounterProxy:
    def __init__(
        self,
        meter: Meter,
        name: str,
        description: str,
        unit: str = '',
        label_cache: dict[frozenset[tuple[str, Any]], 'CounterProxy'] | None = None,
    ):
        self.meter = meter
        self.name = name
        self.description = description
        self.unit = unit

        self.real_counter: Counter = meter.create_counter(
            name,
            description=description,
            unit=unit,
        )
        self._current_attributes: dict[str, Any] | MappingProxyType[str, Any] = {}
        self._label_cache = label_cache if label_cache is not None else {}

    def labels(self, **kwargs: Any) -> 'CounterProxy':
        key = frozenset(kwargs.items())
        if key in self._label_cache:
            return self._label_cache[key]

        proxy = CounterProxy(
            self.meter,
            self.name,
            self.description,
            unit=self.unit,
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


class CounterRegistry:
    def __init__(self, meter: Meter):
        self.meter = meter
        self._counters: dict[str, CounterProxy] = {}

    def counter(self, name: str, description: str, unit: str = '') -> CounterProxy:
        if name not in self._counters:
            self._counters[name] = CounterProxy(
                self.meter,
                name,
                description,
                unit=unit,
            )
        return self._counters[name]
