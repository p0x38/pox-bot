from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import List, Optional

from pytz import UTC

class ServerFeatureType(StrEnum):
    delete_swears = "delete_message_with_swears"
    level_notify = "enable_level_notify"
    anti_spam = "anti_spam_message"
    predefined_auto_reply = "enable_bot_predefined_autoreply"

@dataclass
class BlacklistEntry:
    entry_type: str
    data: str
    reason: Optional[str] = None
    executed_by: int = 0
    timestamp: float = field(default_factory=lambda: datetime.now(UTC).timestamp())

@dataclass
class ServerFeatureEntry:
    name: str
    enabled: bool = False
    updated_by: int = 0
    updated_at: float = field(default_factory=lambda: datetime.now(UTC).timestamp())

@dataclass
class GuildConfig:
    # Blacklists
    blacklist_enabled: bool = False
    blacklists: List[BlacklistEntry] = field(default_factory=list)

    # Leveling
    leveling_enabled: bool = True
    xp_rate: float = 1.0
    
    # Tickets
    ticket_category_id: int = 0
    ticket_master_channel_id: int = 0
    
    # Server features
    features: List[ServerFeatureEntry] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: dict):
        if "blacklists" in data and isinstance(data["blacklists"], list):
            data["blacklists"] = [
                BlacklistEntry(**item) if isinstance(item, dict) else item
                for item in data['blacklists']
            ]
        
        if "features" in data and isinstance(data["features"], list):
            data["features"] = [
                ServerFeatureEntry(**item) if isinstance(item, dict) else item
                for item in data['blacklists']
            ]
        
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict:
        return asdict(self)