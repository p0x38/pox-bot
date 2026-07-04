from typing import Any

from pydantic import BaseModel, Field


class PipelineStep(BaseModel):
    name: str
    kwargs: dict[str, Any] = Field(default_factory=dict)
