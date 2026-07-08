from dataclasses import dataclass, field
from datetime import timedelta
from io import BytesIO
from typing import Any

from pydantic import BaseModel, Field


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, description='Text to convert into audio')
    voice: str | None = Field(None, description='Voice name or Asset path to be used')
    engine_type: str = Field(..., description='The kind of TTS engine should to use')
    extra_options: dict[str, Any] = Field(
        default_factory=dict, description='An additional argument to specify'
    )


@dataclass
class TTSMetricsData:
    duration: timedelta
    char_count: int
    engine_name: str
    chunk_count: int = 0
    success: bool = True
    error_type: str | None = None


@dataclass
class TTSResult:
    output: BytesIO
    media_type: str
    metrics: TTSMetricsData
