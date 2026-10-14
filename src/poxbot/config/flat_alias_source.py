from typing import Any, get_args

from pydantic import BaseModel
from pydantic.fields import FieldInfo
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
)


def _get_model_type(annotation: Any) -> type[BaseModel] | None:
    for candidate in (annotation, *get_args(annotation)):
        if isinstance(candidate, type) and issubclass(candidate, BaseModel):
            return candidate

    return None


def _iter_nested_aliases(
    model: type[BaseModel],
    prefix: tuple[str, ...] = (),
):
    for field_name, field in model.model_fields.items():
        path = (*prefix, field_name)
        nested_model = _get_model_type(field.annotation)

        if nested_model is not None:
            yield from _iter_nested_aliases(nested_model, path)
        elif isinstance(field.validation_alias, str):
            yield path, field.validation_alias


def _set_nested_value(
    data: dict[str, Any],
    path: tuple[str, ...],
    value: Any,
) -> None:
    current = data

    for key in path[:-1]:
        child = current.get(key)

        if not isinstance(child, dict):
            if child is not None:
                return

            child = {}
            current[key] = child

        current = child

    current[path[-1]] = value


class FlatAliasSettingsSource(PydanticBaseSettingsSource):
    def __init__(
        self,
        settings_cls: type[BaseSettings],
        source: PydanticBaseSettingsSource,
    ) -> None:
        super().__init__(settings_cls)
        self.source = source

    def get_field_value(
        self,
        field: FieldInfo,
        field_name: str,
    ) -> tuple[Any, str, bool]:
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        data = self.source()
        env_vars = getattr(self.source, 'env_vars', {})
        case_sensitive = getattr(self.source, 'case_sensitive', False)

        for path, alias in _iter_nested_aliases(self.settings_cls):
            env_name = alias if case_sensitive else alias.lower()

            if env_name in env_vars:
                _set_nested_value(data, path, env_vars[env_name])

        return data
