from dataclasses import dataclass
from enum import StrEnum

from .guild_settings_v2 import GuildConfigV2


class ConfigMutationStatus(StrEnum):
    SUCCESS = 'success'
    NO_CHANGE = 'no_change'
    ALREADY_EXISTS = 'already_exists'
    NOT_FOUND = 'not_found'
    NOT_CONFIGURED = 'not_configured'


@dataclass(frozen=True, slots=True)
class ConfigMutationResult:
    config: GuildConfigV2
    status: ConfigMutationStatus

    @property
    def success(self) -> bool:
        return self.status is ConfigMutationStatus.SUCCESS
