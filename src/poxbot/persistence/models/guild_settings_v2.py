from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum, IntEnum

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


class EEWProviderType(IntEnum):
    jma = 0


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
    pass


@dataclass
class AntiSpamFilter(BaseFilterData):
    messages_per_window: int = 5
    window_length: int = 4


@dataclass
class AntiJoinFilter(BaseFilterData):
    pass


@dataclass
class AntiMessageFilter(BaseFilterData):
    blocked_user_ids: list[int] = field(default_factory=list)


@dataclass
class ProfanityFilter(BaseFilterData):
    use_in_globalchat: bool = True


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
    filters: dict[
        str,
        BaseFilterData
        | AntiSpamFilter
        | WordFilter
        | AntiJoinFilter
        | ProfanityFilter
        | AntiMessageFilter,
    ] = field(
        default_factory=dict,
    )


@dataclass
class TicketConfig(BaseConfigData):
    category: int | None = None
    master_channel: int | None = None
    staff_role: int | None = None


class GlobalChatDeliveryType(IntEnum):
    bot = 0
    webhook = 1


@dataclass
class GlobalChatConfig(BaseConfigData):
    channel_id: int | None = None
    webhook_url: str | None = None
    silent: bool = True
    message_delivery_type: GlobalChatDeliveryType = GlobalChatDeliveryType.bot
    whitelisted_user_ids: list[int] = field(default_factory=list)


@dataclass
class LogsConfig(BaseConfigData):
    channel_id: int | None = None


@dataclass
class UserphoneConfig(BaseConfigData):
    channel_id: int | None = None
    status: PhoneStatus = PhoneStatus.idle
    current_partner_id: int | None = None


class ChatbotMethodType(IntEnum):
    ai = 0
    markov_chain = 1


class MarkovModelScope(Enum):
    GLOBAL = 'global'
    SERVER = 'server'
    USER = 'user'


@dataclass
class ChatbotConfig(BaseConfigData):
    enabled: bool = False
    type: ChatbotMethodType = ChatbotMethodType.ai
    markov_scope: MarkovModelScope = MarkovModelScope.SERVER
    markov_order: int = 2
    markov_max_tokens: int = 50


@dataclass
class GuildConfigV2:
    version: int = 4
    reaction_roles: list[ReactionRoleEntry] = field(default_factory=list)
    features: dict[str, BaseConfigData] = field(default_factory=dict)

    @property
    def filtering(self) -> FilterConfig:
        feat = self.features.get('filtering')
        if not isinstance(feat, FilterConfig):
            feat = FilterConfig()

            self.features['filtering'] = feat
        return feat

    @property
    def leveling(self) -> LevelingConfig:
        feat = self.features.get('leveling')
        if not isinstance(feat, LevelingConfig):
            feat = LevelingConfig()

            self.features['leveling'] = feat
        return feat

    @property
    def welcome(self) -> WelcomeConfig:
        feat = self.features.get('welcome_channel')
        if not isinstance(feat, WelcomeConfig):
            feat = WelcomeConfig()

            self.features['welcome_channel'] = feat
        return feat

    @property
    def tickets(self) -> TicketConfig:
        feat = self.features.get('ticket_system')
        if not isinstance(feat, TicketConfig):
            feat = TicketConfig()

            self.features['ticket_system'] = feat
        return feat

    @property
    def global_chat(self) -> GlobalChatConfig:
        feat = self.features.get('global_chat')

        if not isinstance(feat, GlobalChatConfig):
            feat = GlobalChatConfig()

            self.features['global_chat'] = feat

        return feat

    @property
    def logs(self) -> LogsConfig:
        feat = self.features.get('logs')
        if not isinstance(feat, LogsConfig):
            feat = LogsConfig()
            self.features['logs'] = feat
        return feat

    @property
    def userphone(self) -> UserphoneConfig:
        feat = self.features.get('userphone')
        if not isinstance(feat, UserphoneConfig):
            feat = UserphoneConfig()

            self.features['userphone'] = feat
        return feat

    @property
    def chatbot(self) -> ChatbotConfig:
        feat = self.features.get('chatbot')
        if not isinstance(feat, ChatbotConfig):
            feat = ChatbotConfig()

            self.features['chatbot'] = feat
        return feat

    @classmethod
    def from_dict(cls, data: dict):
        f = data.get('features', {})
        parsed = {}

        w = f.get('welcome_channel', f.get('welcome', {}))
        parsed['welcome_channel'] = WelcomeConfig(
            enabled=w.get('enabled', False),
            last_execution=w.get('last_execution', datetime.now(UTC).timestamp()),
            last_executor=w.get('last_executor'),
            channels=WelcomeChannels(**w.get('channels', {})),
            data=WelcomeData(**w.get('data', {})),
        )

        filt_raw = f.get('filtering', {})
        sub_feats = filt_raw.get('filters', {})

        filter_map = {}
        if 'word' in sub_feats:
            wf = sub_feats['word']
            filter_map['word'] = WordFilter(
                enabled=wf.get('enabled', False),
            )

        if 'anti_join' in sub_feats:
            aj = sub_feats['anti_join']
            filter_map['anti_join'] = AntiJoinFilter(
                enabled=aj.get('enabled', False),
            )

        if 'anti_spam' in sub_feats:
            filter_map['anti_spam'] = AntiSpamFilter(**sub_feats['anti_spam'])

        if 'profanity' in sub_feats:
            pf = sub_feats['profanity']
            filter_map['profanity'] = ProfanityFilter(
                enabled=pf.get('enabled', False),
                use_in_globalchat=pf.get(
                    'use_in_globalchat', pf.get('global_chat', True)
                ),
            )

        if 'anti_message' in sub_feats:
            am = sub_feats['anti_message']
            raw_blocked_user_ids = am.get('blocked_user_ids', [])
            if not isinstance(raw_blocked_user_ids, list):
                raw_blocked_user_ids = []

            blocked_user_ids = [
                int(user_id)
                for user_id in raw_blocked_user_ids
                if (
                    isinstance(user_id, int)
                    and not isinstance(user_id, bool)
                    and user_id > 0
                )
                or (
                    isinstance(user_id, str)
                    and user_id.isdecimal()
                    and int(user_id) > 0
                )
            ]
            filter_map['anti_message'] = AntiMessageFilter(
                enabled=am.get('enabled', False),
                blocked_user_ids=sorted(set(blocked_user_ids)),
            )

        parsed['filtering'] = FilterConfig(
            enabled=filt_raw.get('enabled', False),
            last_execution=filt_raw.get(
                'last_execution',
                datetime.now(UTC).timestamp(),
            ),
            last_executor=filt_raw.get('last_executor'),
            filters=filter_map,
        )

        lv = f.get('leveling', {})
        parsed['leveling'] = LevelingConfig(
            enabled=lv.get('enabled', False),
            last_execution=lv.get('last_execution', datetime.now(UTC).timestamp()),
            last_executor=lv.get('last_executor'),
            xp_rate=lv.get('xp_rate', 1.0),
            notify=lv.get('notify', True),
            notify_channel=lv.get('notify_channel'),
        )

        tk = f.get('ticket_system', {})
        parsed['ticket_system'] = TicketConfig(
            enabled=tk.get('enabled', False),
            last_execution=tk.get('last_execution', datetime.now(UTC).timestamp()),
            last_executor=tk.get('last_executor'),
            category=tk.get('category'),
            master_channel=tk.get('master_channel'),
            staff_role=tk.get('staff_role'),
        )

        phone_raw = f.get('userphone', {})
        parsed['userphone'] = UserphoneConfig(
            enabled=phone_raw.get('enabled', False),
            last_execution=phone_raw.get(
                'last_execution',
                datetime.now(UTC).timestamp(),
            ),
            last_executor=phone_raw.get('last_executor'),
            channel_id=phone_raw.get('channel_id'),
            status=PhoneStatus(phone_raw.get('status', 0)),
            current_partner_id=phone_raw.get('current_partner_id'),
        )

        gc = f.get('global_chat', {})
        delivery_type_raw = gc.get('message_delivery_type', gc.get('delivery_type', 1))
        try:
            delivery_type = GlobalChatDeliveryType(delivery_type_raw)
        except ValueError:
            if isinstance(delivery_type_raw, str):
                candidate = delivery_type_raw.lower()
                if candidate == 'webhook':
                    delivery_type = GlobalChatDeliveryType.webhook
                else:
                    delivery_type = GlobalChatDeliveryType.bot
            else:
                delivery_type = GlobalChatDeliveryType.webhook

        parsed['global_chat'] = GlobalChatConfig(
            enabled=gc.get('enabled', False),
            last_execution=gc.get('last_execution', datetime.now(UTC).timestamp()),
            last_executor=gc.get('last_executor'),
            channel_id=gc.get('channel_id'),
            webhook_url=gc.get('webhook_url'),
            silent=gc.get('silent', True),
            message_delivery_type=delivery_type,
            whitelisted_user_ids=[
                int(user_id)
                for user_id in (gc.get('whitelisted_user_ids') or [])
                if str(user_id).isdigit()
            ],
        )

        logs_raw = f.get('logs', {})
        logs_channel_id = logs_raw.get('channel_id', gc.get('log_channel_id'))
        parsed['logs'] = LogsConfig(
            enabled=logs_raw.get('enabled', logs_channel_id is not None),
            last_execution=logs_raw.get(
                'last_execution',
                datetime.now(UTC).timestamp(),
            ),
            last_executor=logs_raw.get('last_executor'),
            channel_id=logs_channel_id,
        )

        chatbot_raw = f.get('chatbot', {})

        chatbot_type_raw = chatbot_raw.get(
            'type',
            ChatbotMethodType.ai,
        )

        try:
            chatbot_type = ChatbotMethodType(
                chatbot_type_raw,
            )
        except (ValueError, TypeError):
            if isinstance(chatbot_type_raw, str):
                try:
                    chatbot_type = ChatbotMethodType[chatbot_type_raw.lower()]
                except KeyError:
                    chatbot_type = ChatbotMethodType.ai
            else:
                chatbot_type = ChatbotMethodType.ai

        markov_scope_raw = chatbot_raw.get(
            'markov_scope',
            MarkovModelScope.SERVER.value,
        )

        try:
            markov_scope = MarkovModelScope(markov_scope_raw)
        except (ValueError, TypeError):
            markov_scope = MarkovModelScope.SERVER

        parsed['chatbot'] = ChatbotConfig(
            enabled=chatbot_raw.get('enabled', False),
            last_execution=chatbot_raw.get(
                'last_execution',
                datetime.now(UTC).timestamp(),
            ),
            last_executor=chatbot_raw.get('last_executor'),
            type=chatbot_type,
            markov_scope=markov_scope,
            markov_order=chatbot_raw.get('markov_order', 2),
            markov_max_tokens=chatbot_raw.get('markov_max_tokens', 50),
        )

        return cls(
            version=data.get('version', 4),
            reaction_roles=[
                ReactionRoleEntry(**entry)
                for entry in (data.get('reaction_roles') or [])
            ],
            features=parsed,
        )

    def to_dict(self) -> dict:
        return asdict(self)
