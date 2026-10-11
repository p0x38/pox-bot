import csv
from abc import ABC, abstractmethod
from io import StringIO
from typing import Any, ClassVar, TypeVar

T = TypeVar('T')


class Converter(ABC):
    @abstractmethod
    def convert(self, value: Any) -> Any:
        """Convert a value into the target type."""
        raise NotImplementedError


class StringConverter(Converter):
    def convert(self, value: Any) -> str:
        return str(value)


class IntegerConverter(Converter):
    def convert(self, value: Any) -> int:
        return int(value)


class FloatConverter(Converter):
    def convert(self, value: Any) -> float:
        return float(value)


class BooleanConverter(Converter):
    TRUE_VALUES: ClassVar[set] = {'true', '1', 'yes', 'on'}
    FALSE_VALUES: ClassVar[set] = {'false', '0', 'no', 'off'}

    def convert(self, value: Any) -> bool:
        if not isinstance(value, str):
            return bool(value)

        normalized = value.strip().lower()

        if normalized in self.TRUE_VALUES:
            return True

        if normalized in self.FALSE_VALUES:
            return False

        raise ValueError(f'Cannot convert {value!r} to bool')


class CollectionConverter(Converter):
    def _items(self, value: Any) -> list[Any]:
        if isinstance(value, str):
            return next(csv.reader(StringIO(value), skipinitialspace=True))

        return list(value)


class ListConverter(CollectionConverter):
    def convert(self, value: Any) -> list[Any]:
        return self._items(value)


class TupleConverter(CollectionConverter):
    def convert(self, value: Any) -> tuple[Any, ...]:
        return tuple(self._items(value))


class SetConverter(CollectionConverter):
    def convert(self, value: Any) -> set[Any]:
        return set(self._items(value))


class Parser:
    _converters: ClassVar[dict[type, Converter]] = {
        str: StringConverter(),
        int: IntegerConverter(),
        float: FloatConverter(),
        bool: BooleanConverter(),
        list: ListConverter(),
        tuple: TupleConverter(),
        set: SetConverter(),
    }

    @classmethod
    def register(cls, output: type, converter: Converter) -> None:
        cls._converters[output] = converter

    @classmethod
    def convert(cls, input_data: Any, output: type[T]) -> T:
        try:
            converter = cls._converters[output]
        except KeyError:
            raise TypeError(f'Unsupported output type: {output!r}') from None

        return converter.convert(input_data)
