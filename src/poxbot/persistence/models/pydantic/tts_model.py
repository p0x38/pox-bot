from __future__ import annotations

from pathlib import Path
from typing import Annotated

from pydantic import AfterValidator, BaseModel, RootModel

from ....shared.enums.tts import TTSEngineType

BASE_ASSETS_PATH = Path(__file__).resolve().parent.parent.parent.parent / "assets"


def resolve_voice_path(v: Path) -> Path:
    if not v.is_absolute():
        full_path = BASE_ASSETS_PATH / v
        return full_path
    return v


ResolvedPath = Annotated[Path, AfterValidator(resolve_voice_path)]


class ModelInfo(BaseModel):
    name: str
    friendly_name: str
    model: ResolvedPath


class TTSConfig(RootModel):
    root: dict[TTSEngineType, dict[str, list[ModelInfo]]]
