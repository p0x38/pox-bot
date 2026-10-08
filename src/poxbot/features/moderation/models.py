from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

from .normalization import normalize_domain, normalize_text


class ThreatReason(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid')

    category: str = Field(min_length=1, max_length=64, pattern=r'^[a-z0-9_]+$')
    description: str = Field(min_length=1, max_length=300)


class ThreatIndicator(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid')

    id: str = Field(min_length=1, max_length=100)
    type: Literal['image_hash', 'url_domain', 'text_phrase']
    algorithm: Literal['sha256', 'phash'] | None = None
    value: str = Field(min_length=1, max_length=2048)
    reason: ThreatReason
    confidence: float = Field(ge=0.0, le=1.0)
    status: Literal['pending', 'confirmed', 'rejected'] = 'pending'
    source: str = Field(min_length=1, max_length=100)
    created_at: datetime
    reviewed_at: datetime | None = None
    expires_at: datetime | None = None
    max_distance: int | None = Field(default=None, ge=0, le=64)
    metadata: dict[str, str] = Field(default_factory=dict)

    @field_validator('created_at', 'reviewed_at', 'expires_at')
    @classmethod
    def require_timezone_aware(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError('Threat indicator timestamps must include a timezone')
        return value

    @field_validator('value')
    @classmethod
    def validate_value(cls, value: str, info: ValidationInfo) -> str:
        indicator_type = info.data.get('type')
        algorithm = info.data.get('algorithm')

        if indicator_type == 'image_hash':
            if algorithm == 'sha256':
                if len(value) != 64 or any(
                    char not in '0123456789abcdefABCDEF' for char in value
                ):
                    raise ValueError(
                        'SHA-256 values must contain 64 hexadecimal characters'
                    )
                return value.lower()
            if algorithm == 'phash':
                if len(value) != 16 or any(
                    char not in '0123456789abcdefABCDEF' for char in value
                ):
                    raise ValueError(
                        '64-bit pHash values must contain 16 hexadecimal characters'
                    )
                return value.lower()
        elif indicator_type == 'url_domain':
            return normalize_domain(value)
        elif indicator_type == 'text_phrase':
            normalized = normalize_text(value).strip()
            if not normalized:
                raise ValueError('Text phrases cannot be empty after normalization')
            return normalized

        return value

    @model_validator(mode='after')
    def validate_indicator_fields(self):
        if self.type == 'image_hash':
            if self.algorithm is None:
                raise ValueError('Image hash indicators require an algorithm')
            if self.algorithm == 'phash' and self.max_distance is None:
                raise ValueError('pHash indicators require max_distance')
            if self.algorithm == 'sha256' and self.max_distance is not None:
                raise ValueError('SHA-256 indicators cannot set max_distance')
        elif self.algorithm is not None or self.max_distance is not None:
            raise ValueError('Only image hash indicators can set hash fields')

        if self.status == 'confirmed' and self.reviewed_at is None:
            raise ValueError('Confirmed indicators require reviewed_at')
        if self.expires_at is not None and self.expires_at <= self.created_at:
            raise ValueError('expires_at must be later than created_at')
        return self


class ThreatCatalog(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid')

    schema_version: Literal[1]
    indicators: tuple[ThreatIndicator, ...] = ()

    @model_validator(mode='after')
    def ensure_unique_ids(self):
        ids = [indicator.id for indicator in self.indicators]
        if len(ids) != len(set(ids)):
            raise ValueError('Threat indicator IDs must be unique')
        return self


class ModerationAction(StrEnum):
    ALLOW = 'allow'
    BLOCK = 'block'
    REVIEW = 'review'


@dataclass(frozen=True)
class ModerationEvidence:
    reason_code: str
    description: str
    indicator_id: str | None = None
    confidence: float | None = None
    match_type: str = 'rule'
    action: ModerationAction = ModerationAction.BLOCK


@dataclass(frozen=True)
class ModerationResult:
    action: ModerationAction
    evidence: tuple[ModerationEvidence, ...] = ()

    @property
    def reason_codes(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(item.reason_code for item in self.evidence))

    @classmethod
    def allow(cls) -> 'ModerationResult':
        return cls(action=ModerationAction.ALLOW)

    @classmethod
    def review(cls, reason_code: str, description: str) -> 'ModerationResult':
        return cls(
            action=ModerationAction.REVIEW,
            evidence=(
                ModerationEvidence(
                    reason_code,
                    description,
                    action=ModerationAction.REVIEW,
                ),
            ),
        )


def combine_results(*results: ModerationResult) -> ModerationResult:
    evidence = tuple(item for result in results for item in result.evidence)
    if any(item.action == ModerationAction.BLOCK for item in evidence):
        return ModerationResult(action=ModerationAction.BLOCK, evidence=evidence)
    if any(item.action == ModerationAction.REVIEW for item in evidence):
        return ModerationResult(action=ModerationAction.REVIEW, evidence=evidence)
    return ModerationResult.allow()


def indicator_is_active(
    indicator: ThreatIndicator,
    now: datetime | None = None,
) -> bool:
    if indicator.status == 'rejected':
        return False
    return indicator.expires_at is None or indicator.expires_at > (
        now or datetime.now(UTC)
    )
