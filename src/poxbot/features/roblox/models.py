from __future__ import annotations

import math
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

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError('Question ID cannot be empty.')

        if not self.feature.strip():
            raise ValueError('Question feature cannot be empty.')

        if not self.prompt.strip():
            raise ValueError('Question prompt cannot be empty.')

        if isinstance(self.weight, bool) or not isinstance(self.weight, (int, float)):
            raise TypeError('Question weight must be a number.')

        if not math.isfinite(self.weight) or self.weight <= 0:
            raise ValueError('Question weight must be finite and positive.')


@dataclass(frozen=True, slots=True)
class RobloxCandidate:
    user_id: int
    username: str
    display_name: str
    features: dict[str, FeatureValue]
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.user_id, bool) or self.user_id <= 0:
            raise ValueError('Candidate user ID must be positive.')

        if not isinstance(self.username, str) or not self.username.strip():
            raise ValueError('Candidate username cannot be empty.')

        if not isinstance(self.display_name, str) or not self.display_name.strip():
            raise ValueError('Candidate display name cannot be empty.')

        if any(
            not isinstance(feature, str) or not feature for feature in self.features
        ):
            raise ValueError('Candidate feature keys must be non-empty strings.')

        if any(
            value is not None and type(value) is not bool
            for value in self.features.values()
        ):
            raise TypeError('Candidate feature values must be bool or None.')

        if any(not isinstance(tag, str) or not tag for tag in self.tags):
            raise ValueError('Candidate tags must be non-empty strings.')


@dataclass(frozen=True, slots=True)
class QuestionData:
    version: Literal[1]
    questions: tuple[Question, ...]


@dataclass(frozen=True, slots=True)
class CandidateData:
    version: Literal[1]
    candidates: tuple[RobloxCandidate, ...]
