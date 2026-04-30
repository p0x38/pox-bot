from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import IntEnum
import uuid

from pytz import UTC

@dataclass
class BaseConfigData:
    enabled: bool = False
    last_execution: float = field(default_factory=lambda: datetime.now(UTC).timestamp())
    last_executor: int | None = None

@dataclass
class BaseFilterData:
    enabled: bool = False

@dataclass
class WelcomeChannels:
    join: int | None = 0
    leave: int | None = 0
    rules: int | None = 0

class PhoneStatus(IntEnum):
    idle = 0
    searching = 1
    in_call = 2

class BlacklistEntryMatchType(IntEnum):
    default = 0
    regex = 1
    exact = 2
    whole_word = 3

@dataclass
class BlacklistEntry:
    trigger: str
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    reason: str | None = None
    type: BlacklistEntryMatchType = BlacklistEntryMatchType.default
    case_insensitive: bool = True
    executed_by: int | None = 0
    timestamp: float = field(default_factory=lambda: datetime.now(UTC).timestamp())

@dataclass
class ReactionRoleEntry:
    message_id: int
    emoji: str
    role_id: int

@dataclass
class WelcomeData:
    welcome_message: str | None = None
    leave_message: str | None = None

@dataclass
class WordFilter(BaseFilterData):
    blacklists: list[BlacklistEntry] = field(default_factory=list)

@dataclass
class AntiSpamFilter(BaseFilterData):
    messages_per_window: int = 5
    window_length: int = 4

@dataclass
class WelcomeConfig(BaseConfigData):
    channels: WelcomeChannels = field(default_factory=WelcomeChannels)
    data: WelcomeData = field(default_factory=WelcomeData)

@dataclass
class LevelingConfig(BaseConfigData):
    xp_rate: float = 1.0
    notify: bool = True
    notify_channel: int | None = None

@dataclass
class FilterConfig(BaseConfigData):
    filters: dict[str, BaseFilterData | AntiSpamFilter | WordFilter] = field(default_factory=dict)

@dataclass
class TicketConfig(BaseConfigData):
    category: int | None = None
    master_channel: int | None = None
    staff_role: int | None = None

@dataclass
class GlobalChatConfig(BaseConfigData):
    channel_id: int | None = None
    webhook_url: str | None = None

@dataclass
class UserphoneConfig(BaseConfigData):
    channel_id: int | None = None
    status: PhoneStatus = PhoneStatus.idle
    current_partner_id: int | None = None

@dataclass
class GuildConfigV2:
    version: int = 2
    reaction_roles: list[ReactionRoleEntry] = field(default_factory=list)
    features: dict[str, BaseConfigData] = field(default_factory=dict)
    
    @property
    def filtering(self) -> FilterConfig:
        feat = self.features.get("filtering")
        if not isinstance(feat, FilterConfig):
            return FilterConfig()
        return feat
    
    @property
    def leveling(self) -> LevelingConfig:
        feat = self.features.get("leveling")
        if not isinstance(feat, LevelingConfig):
            return LevelingConfig()
        return feat
    
    @property
    def welcome(self) -> WelcomeConfig:
        feat = self.features.get("welcome_channel")
        if not isinstance(feat, WelcomeConfig):
            return WelcomeConfig()
        return feat
    
    @property
    def tickets(self) -> TicketConfig:
        feat = self.features.get("ticket_system")
        if not isinstance(feat, TicketConfig):
            return TicketConfig()
        return feat
    
    @property
    def global_chat(self) -> GlobalChatConfig:
        feat = self.features.get("global_chat")
        if not isinstance(feat, GlobalChatConfig):
            return GlobalChatConfig()
        return feat
    
    @property
    def userphone(self) -> UserphoneConfig:
        feat = self.features.get("global_chat")
        if not isinstance(feat, UserphoneConfig):
            return UserphoneConfig()
        return feat
    
    @classmethod
    def from_dict(cls, data: dict):
        f = data.get("features", {})
        parsed = {}
        
        w = f.get("welcome_channel", {})
        parsed["welcome_channel"] = WelcomeConfig(
            enabled=w.get("enabled", False),
            last_execution=w.get("last_execution", datetime.now(UTC).timestamp()),
            last_executor=w.get("last_executor"),
            channels=WelcomeChannels(**w.get("channels", {})),
            data=WelcomeData(**w.get("data", {}))
        )
        
        filt_raw = f.get("filtering", {})
        sub_feats = filt_raw.get("filters", {})
        
        filter_map = {}
        if "word" in sub_feats:
            wf = sub_feats["word"]
            bl = []
            for b in wf.get("blacklists", []):
                match_type_val = b.get("type", 0)
                try:
                    match_type = BlacklistEntryMatchType(match_type_val)
                except ValueError:
                    match_type = BlacklistEntryMatchType.default
                
                bl.append(BlacklistEntry(
                    trigger=b.get("trigger", ""),
                    id=b.get("id", str(uuid.uuid4())[:8]),
                    reason=b.get("reason"),
                    type=match_type,
                    case_insensitive=b.get("case_insensitive", True),
                    executed_by=b.get("executed_by"),
                    timestamp=b.get("timestamp", datetime.now(UTC).timestamp())
                ))
            filter_map["word"] = WordFilter(enabled=wf.get("enabled", False), blacklists=bl)
        
        if "anti_spam" in sub_feats:
            filter_map["anti_spam"] = AntiSpamFilter(**sub_feats["anti_spam"])
        
        parsed["filtering"] = FilterConfig(
            enabled=filt_raw.get("enabled", False),
            last_execution=filt_raw.get("last_execution", datetime.now(UTC).timestamp()),
            last_executor=filt_raw.get("last_executor"),
            filters=filter_map
        )
        
        lv = f.get("levling", {})
        parsed["leveling"] = LevelingConfig(
            enabled=lv.get("enabled", False),
            last_execution=lv.get("last_execution", datetime.now(UTC).timestamp()),
            last_executor=lv.get("last_executor"),
            xp_rate=lv.get("xp_rate", 1.0),
            notify=lv.get("notify", True),
            notify_channel=lv.get("notify_channel")
        )
        
        tk = f.get("ticket_system", {})
        parsed["ticket_system"] = TicketConfig(
            enabled=tk.get("enabled", False),
            last_execution=tk.get("last_execution", datetime.now(UTC).timestamp()),
            last_executor=tk.get("last_executor"),
            category=tk.get("category"),
            master_channel=tk.get("master_channel"),
            staff_role=tk.get("staff_role")
        )
        
        phone_raw = f.get("userphone", {})
        parsed["userphone"] = UserphoneConfig(
            enabled=phone_raw.get("enabled", False),
            last_execution=phone_raw.get("last_execution", datetime.now(UTC).timestamp()),
            last_executor=phone_raw.get("last_executor"),
            channel_id=phone_raw.get("channel_id"),
            status=PhoneStatus(phone_raw.get("status", 0)),
            current_partner_id=phone_raw.get("current_partner_id")
        )
        
        gc = f.get("global_chat", {})
        parsed["global_chat"] = GlobalChatConfig(
            enabled=gc.get("enabled", False),
            last_execution=gc.get("last_execution", datetime.now(UTC).timestamp()),
            last_executor=gc.get("last_executor"),
            channel_id=gc.get("channel_id"),
            webhook_url=gc.get("webhook_url")
        )
        
        return cls(version=data.get("version", 2), features=parsed)
    def to_dict(self) -> dict:
        return asdict(self)