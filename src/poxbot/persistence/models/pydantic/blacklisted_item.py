from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BlacklistReason(StrEnum):
    LOCAL_DOMAIN = 'local_domain'
    IP_LOGGER = 'ip_logger'
    URL_SHORTENER = 'url_shorteners'
    NOT_SPECIFIED = 'unknown'


class BlacklistItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: Any
    reasons: tuple[tuple[BlacklistReason, str], ...] = Field(
        default_factory=lambda: ((BlacklistReason.NOT_SPECIFIED, 'No reason provided'),)
    )

    def __init__(self, *args, **kwargs):
        if args and isinstance(args[0], dict):
            kwargs = {**args[0], **kwargs}
            args = ()

            if 'reasons' in kwargs and isinstance(kwargs['reasons'], dict):
                kwargs['reasons'] = tuple(kwargs['reasons'].items())

        super().__init__(*args, **kwargs)

    @field_validator('reasons', mode='after')
    @classmethod
    def ensure_not_empty(
        cls, v: tuple[tuple[BlacklistReason, str], ...]
    ) -> tuple[tuple[BlacklistReason, str], ...]:
        if not v:
            return ((BlacklistReason.NOT_SPECIFIED, "No reason provided"),)
        return v

    def __hash__(self) -> int:
        return hash(self.value)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, BlacklistItem):
            return False

        return self.value == other.value
