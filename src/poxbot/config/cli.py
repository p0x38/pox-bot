from __future__ import annotations

import asyncio
import sys
from argparse import Namespace
from collections.abc import Callable
from pathlib import Path
from typing import cast, get_args, get_origin

import orjson
from dotenv import dotenv_values
from pydantic import BaseModel, ValidationError

from .manager import ConfigManager
from .schema import BotSettings


def _model_field_names(model: type[BaseModel], prefix: str = '') -> set[str]:
    names: set[str] = set()

    for field_name, field in model.model_fields.items():
        name = f'{prefix}{field_name}'.upper()
        names.add(name)

        annotation = field.annotation
        candidates = (annotation, *get_args(annotation))
        for candidate in candidates:
            origin = get_origin(candidate)
            nested_model = (
                candidate
                if isinstance(candidate, type) and issubclass(candidate, BaseModel)
                else None
            )
            if (
                nested_model is None
                and isinstance(origin, type)
                and issubclass(origin, BaseModel)
            ):
                nested_model = origin
            if nested_model is not None:
                names.update(_model_field_names(nested_model, f'{name}__'))

    return names


def _environment_file(namespace: Namespace) -> Path:
    return Path(getattr(namespace, 'env_file', '.env')).expanduser()


def _check_environment(env_file: Path) -> list[str]:
    errors: list[str] = []
    known_names = _model_field_names(BotSettings)
    values = dotenv_values(env_file) if env_file.is_file() else {}

    unknown_names = sorted(
        name for name in values if name and name.upper() not in known_names
    )
    if unknown_names:
        errors.append(f'Unknown variable(s) in {env_file}: {", ".join(unknown_names)}')

    settings_factory = cast(Callable[..., BotSettings], BotSettings)

    try:
        settings_factory(
            _env_file=env_file if env_file.is_file() else None,
        )
    except ValidationError as exc:
        errors.append(f'Invalid environment configuration: {exc}')

    return errors


def _print_errors(errors: list[str], heading: str) -> None:
    if not errors:
        return

    print(heading, file=sys.stderr)  # ruff: ignore[print]
    for error in errors:
        print(f' - {error}', file=sys.stderr)  # ruff: ignore[print]


def show_config(namespace: Namespace) -> None:
    """Print the current configuration without starting the bot."""

    try:
        settings = asyncio.run(ConfigManager.get_settings())

        data = settings.model_dump(mode='json', exclude={'db_url'})

        if namespace.json:
            output = orjson.dumps(
                data,
                option=orjson.OPT_INDENT_2,
            )
            sys.stdout.buffer.write(output + b'\n')
        else:
            print(  # ruff: ignore[print]
                orjson.dumps(
                    data,
                    option=orjson.OPT_INDENT_2,
                ).decode()
            )

    except (ValidationError, RuntimeError, OSError) as exc:
        print(f'Failed to load configuration: {exc}', file=sys.stderr)  # ruff: ignore[print]
        raise SystemExit(1) from exc


def validate_config(namespace: Namespace) -> None:
    """Validate the current configuration without starting the bot."""

    errors: list[str] = []

    try:
        asyncio.run(ConfigManager.get_settings())
    except (ValidationError, RuntimeError, OSError) as exc:
        errors.append(f'Configuration validation failed: {exc}')

    errors.extend(_check_environment(_environment_file(namespace)))
    _print_errors(errors, 'Configuration validation failed:')
    if errors:
        raise SystemExit(1)

    print('Configuration is valid.')  # ruff: ignore[print]


def check_environment(namespace: Namespace) -> None:
    env_file = _environment_file(namespace)
    errors = _check_environment(env_file)
    _print_errors(errors, 'Environment variable check failed:')
    if errors:
        raise SystemExit(1)

    print(f'Environment variables in {env_file} are valid.')  # ruff: ignore[print]
