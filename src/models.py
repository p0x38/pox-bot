from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import StrEnum
from turtle import st
from typing import Any, Dict, List, Optional, Union, cast

from PIL.Image import item
import orjson
from pytz import UTC

@dataclass
class SettingsData:
    _locale: str = field(default="en", repr=False)
    embed_color: str = "#aaaa00"
    
    def __post_init__(self):
        self.locale = self._locale
    
    @property
    def locale(self) -> str:
        return self._locale
    
    @locale.setter
    def locale(self, value):
        if isinstance(value, list):
            value = value[0] if value else "en"
        elif not isinstance(value, str):
            value = "en"
        
        self._locale = value
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "locale": str(self.locale),
            "embed_color": self.embed_color
        }
    
    @classmethod
    def from_dict(cls, data: Union[Dict[str, Any], str, bytes]):
        if isinstance(data, (str, bytes)):
            parsed_data: Dict[str, Any] = orjson.loads(data)
        else:
            parsed_data = cast(Dict[str, Any], data)
        
        filtered = {
            k: parsed_data[k]
            for k in cls.__dataclass_fields__
            if k in parsed_data
        }

        return cls(**filtered)

@dataclass
class EconomyData:
    user_id: int = 0
    wallet: int = 0
    bank: int = 0
    last_daily: int = 0
    last_work: int = 0

    @property
    def total(self) -> int:
        return self.wallet + self.bank
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "wallet": self.wallet,
            "bank": self.bank,
            "last_daily": self.last_daily,
            "last_work": self.last_work
        }
    
    @classmethod
    def from_dict(cls, data: Union[Dict[str, Any], str, bytes]):
        if isinstance(data, (str, bytes)):
            parsed_data: Dict[str, Any] = orjson.loads(data)
        else:
            parsed_data = cast(Dict[str, Any], data)
        
        filtered = {
            k: parsed_data[k]
            for k in cls.__dataclass_fields__
            if k in parsed_data
        }
        return cls(**filtered)
    
    @classmethod
    def from_row(cls, row):
        if not row: return cls()
        return cls.from_dict(dict(row))

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