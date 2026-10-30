from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

type FeatureValue = bool | None


@dataclass(frozen=True, slots=True)
class Question:
    id: str
    feature: str
    prompt: str
    enabled: bool = True
    weight: float = 1.0


@dataclass(frozen=True, slots=True)
class RobloxCandidate:
    user_id: int
    username: str
    display_name: str
    features: dict[str, FeatureValue]
    tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class QuestionData:
    version: Literal[1]
    questions: tuple[Question, ...]


@dataclass(frozen=True, slots=True)
class CandidateData:
    version: Literal[1]
    candidates: tuple[RobloxCandidate, ...]
