from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from pytz import UTC


@dataclass
class BaseConfigData:
    enabled: bool = False

@dataclass
class BaseFilterData:
    enabled: bool = False

@dataclass
class WelcomeChannels:
    join: Optional[int] = 0
    leave: Optional[int] = 0
    rules: Optional[int] = 0

@dataclass
class BlacklistEntry:
    trigger: str
    reason: Optional[str] = None
    executed_by: int = 0
    timestamp: float = field(default_factory=lambda: datetime.now(UTC).timestamp())

@dataclass
class WelcomeData:
    welcome_message: Optional[str] = None
    leave_message: Optional[str] = None

@dataclass
class WordFilter(BaseFilterData):
    blacklists: List[BlacklistEntry] = field(default_factory=list)

@dataclass
class AntiSpamFilter(BaseFilterData):
    messages_per_window: int = 5
    window_length: int = 4

@dataclass
class WelcomeConfig(BaseConfigData):
    enabled = False
    channels: WelcomeChannels = field(default_factory=WelcomeChannels)
    data: WelcomeData = field(default_factory=WelcomeData)

@dataclass
class LevelingConfig(BaseConfigData):
    xp_rate: float = 1.0
    notify: bool = True
    notify_channel: Optional[int] = None

@dataclass
class FilterConfig(BaseConfigData):
    filters: Dict[str, BaseFilterData] = field(default_factory=dict)

@dataclass
class TicketConfig(BaseConfigData):
    category: Optional[int] = None
    master_channel: Optional[int] = None

@dataclass
class GuildConfigV2:
    features: Dict[str, BaseConfigData] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: dict):
        f = data.get("features", {})
        parsed = {}
        
        if "welcome_channel" in f:
            w = f["welcome_channel"]
            parsed["welcome_channel"] = WelcomeConfig(
                enabled=w.get("enabled", False),
                channels=WelcomeChannels(**w.get("channels", {})),
                data=WelcomeData(**w.get("data", {}))
            )
        
        if "filtering" in f:
            filt_raw = f["filtering"]
            sub_feats = filt_raw.get("features", {})
            
            filter_map = {}
            if "word" in sub_feats:
                wf = sub_feats["word"]
                bl = [BlacklistEntry(**b) for b in wf.get("blacklists", [])]
                filter_map["word"] = WordFilter(enabled=wf.get("enabled", False), blacklists=bl)
            
            if "antispam" in sub_feats:
                filter_map["anti_spam"] = AntiSpamFilter(**sub_feats["antispam"])
            
            parsed["filtering"] = FilterConfig(
                enabled=filt_raw.get("enabled", False),
                filters=filter_map
            )
        
        if "leveling" in f:
            parsed["leveling"] = LevelingConfig(**f["leveling"])
        if "ticket_system" in f:
            parsed["ticket_system"] = TicketConfig(**f["ticket_system"])
        
        return cls(features=parsed)
    
    def to_dict(self) -> dict:
        return asdict(self)