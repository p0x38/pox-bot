from __future__ import annotations

from pathlib import Path
from typing import Annotated

from pydantic import AfterValidator, BaseModel, RootModel

from ....core.resources import create_default_resource_manager
from ....shared.enums.tts import TTSEngineType

_RESOURCE_PATHS = create_default_resource_manager()


def resolve_voice_path(v: Path) -> Path:
    value = str(v)

    if value.startswith("assets:"):
        return _RESOURCE_PATHS.resolve_path(value)

    if not v.is_absolute():
        return _RESOURCE_PATHS.resolve_path(f"assets:{v.as_posix()}")

    return v


ResolvedPath = Annotated[Path, AfterValidator(resolve_voice_path)]


class ModelInfo(BaseModel):
    name: str
    friendly_name: str
    model: ResolvedPath


class TTSConfig(RootModel):
    root: dict[TTSEngineType, dict[str, list[ModelInfo]]]
