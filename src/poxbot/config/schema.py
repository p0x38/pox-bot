import re
from pathlib import Path
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    computed_field,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings.sources import PydanticBaseSettingsSource
from sqlalchemy import URL

from ..shared.utils.app_path import app_dir
from .flat_alias_source import FlatAliasSettingsSource

_PIPER_VOICE_ID_PATTERN = re.compile(
    r'^[a-z]{2,3}_[A-Z]{2}-[A-Za-z0-9_]+-[A-Za-z0-9_-]+$',
)


class PiperTTSConfig(BaseModel):
    """Define configuration settings for Piper TTS.

    Attributes:
        default_voice: The default voice for Piper voice.
        allowed_voices: The list of voices which is allowed to use.

    Raises:
        pydantic.ValidationError: Raised when validation fails for any of the following:
            - `allowed_voices` is empty.
            - one of `allowed_voices` value has including an invalid character(s).
            - `default_voice` hasn't included in `allowed_voices`.
    """

    default_voice: str = 'en_US-john-medium'
    allowed_voices: list[str] = Field(
        default_factory=lambda: [
            'en_US-danny-low',
            'en_US-hfc_male-medium',
            'en_US-john-medium',
            'en_US-lessac-medium',
            'en_US-ljspeech-high',
            'en_US-ryan-low',
            'en_US-ryan-medium',
            'en_US-ryan-high',
            'ja_JP-hi_fi_captain-medium',
        ],
    )

    @field_validator('allowed_voices')
    @classmethod
    def validate_allowed_voices(cls, voices: list[str]) -> list[str]:
        voices = list(dict.fromkeys(voice.strip() for voice in voices))

        if not voices:
            raise ValueError('At least one Piper voice must be allowed.')

        invalid_voices = [
            voice for voice in voices if not _PIPER_VOICE_ID_PATTERN.fullmatch(voice)
        ]

        if invalid_voices:
            raise ValueError(
                f'Invalid Piper voice identifiers: {invalid_voices!r}',
            )

        return voices

    @model_validator(mode='after')
    def validate_default_voice(self) -> 'PiperTTSConfig':
        if self.default_voice not in self.allowed_voices:
            raise ValueError(
                'The default Piper voice must be included in allowed_voices.',
            )

        return self


class DatabaseConfig(BaseModel):
    """Represent configuration parameters required to establish a database connection.

    This Pydantic model holds the database connection settings, including credentials,
    host parameters, and the backend driver specifications.

    Attributes:
        host: The IP address or hostname of the database server.
        port: The port number on which the database server is listening.
        user: The username utilized for database authentication.
        password: The sensitive password wrapper for authentication.
        name: The name of the target database instance.
        driver: The specific SQLAlchemy dialect and async driver combination.
    """

    host: str = '127.0.0.1'
    port: int = 5432
    user: str = 'postgres'
    password: SecretStr = SecretStr('postgres')
    name: str = 'postgres'
    driver: str = 'postgresql+asyncpg'

    def build_url(self) -> str:
        """Generate a Data Source Name (DSN) for SQLAlchemy connection strings.

        Assemble the individual connection components into a unified URL format suitable
        for creating an asynchronous database engine.

        Returns:
            The fully rendered DSN connection string.
        """

        url_object = URL.create(
            drivername=self.driver,
            username=self.user,
            password=self.password.get_secret_value(),
            host=self.host,
            port=self.port,
            database=self.name,
        )

        return url_object.render_as_string(hide_password=False)


class FileLoggingConfig(BaseModel):
    """Define configuration settings for exporting logs directly to file storage.

    Attributes:
        enabled: Toggle status to control whether file logging is active.
        directory: The destination file path directory where logs are stored.
        encoding: The text encoding method applied to generated log files.
    """

    enabled: bool = True
    directory: Path = Field(default=app_dir.user_log_path)
    encoding: str = 'utf-8'


class ConsoleLoggingConfig(BaseModel):
    """Define configuration metrics for terminal-based log presentation.

    Attributes:
        enabled: The toggle for visibility to show/hide logs.
        rich_tracebacks: Toggle status to enable advanced terminal tracebacks.
        level: The threshold logging level for standard output.
        markup: Toggle status to support inline console formatting tags.
    """

    enabled: bool = True
    rich_tracebacks: bool = True
    level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] = 'INFO'
    markup: bool = True


class LoggerConfig(BaseModel):
    """Manage systemic logging behavior across console and file channels.

    Attributes:
        enabled: The toggle for visibility to enable logging.
        level: The root logging severity for the application.
        file_logging: Dedicated settings for file log output.
        console_logging: Dedicated settings for console log output.
    """

    enabled: bool = True
    level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] = 'DEBUG'
    file_logging: FileLoggingConfig = Field(default_factory=FileLoggingConfig)
    console_logging: ConsoleLoggingConfig = Field(default_factory=ConsoleLoggingConfig)


class TokenConfig(BaseModel):
    """Store critical integration tokens and authorization keys securely.

    Attributes:
        discord_token: Protected API token for the Discord bot client.
        lmstudio_token: Protected access key for local LM-Studio instances.
        openai_api_key: Protected developer key for OpenAI endpoints.
        openrouter_api_key: Protected provider key for OpenRouter routing.
    """

    discord_token: SecretStr = SecretStr('')
    lmstudio_token: SecretStr = SecretStr('')
    openai_api_key: SecretStr = SecretStr('')
    openrouter_api_key: SecretStr = SecretStr('')


class TraceConfig(BaseModel):
    """Govern OpenTelemetry tracing, metric collection, and observability.

    Attributes:
        enabled: Toggle status to activate or disable system telemetry tracking.
        opentelemetry_endpoint: Base destination URI for OTLP collectors.
        otlp_traces_endpoint: Explicit endpoint target for processing traces.
        otlp_metrics_endpoint: Explicit endpoint for collecting metrics.
        loki_url: Target endpoint for dispatching collected logs to Grafana Loki.
        prometheus_host: The local network interface address for Prometheus metrics.
        prometheus_server_port: The local port assigned to the Prometheus metrics
            server.
        insecure: Toggle status to bypass TLS validation for telemetry endpoints.
        sampling_ratio: The target proportion of requests to trace.
        export_interval_ms: The frequency delay between batch data exports.
        max_batch_size: The maximum buffer volume of items sent per export cycle.
    """

    enabled: bool = True
    opentelemetry_endpoint: str = 'http://127.0.0.1:4317'
    otlp_traces_endpoint: str | None = None
    otlp_metrics_endpoint: str | None = None
    loki_url: str = 'http://127.0.0.1:3100/loki/api/v1/push'
    prometheus_host: str = '0.0.0.0'
    prometheus_server_port: int = 8001
    insecure: bool = True
    sampling_ratio: float = Field(default=1.0, ge=0.0, le=1.0)
    export_interval_ms: int = 1000 * 15
    max_batch_size: int = 512


class LLMConfig(BaseModel):
    """Represent setting parameters allocated for language model behaviors.

    Attributes:
        provider_type: The configured LLM provider identifier.
        model_id: The identifier tag of the targeted model variant.
    """

    provider_type: Literal['openrouter', 'ollama', 'gemini', 'openai'] = 'openrouter'
    model_id: str = ''


class BotCustomConfig(BaseModel):
    """A config model for bot itself.

    Attributes:
        bot_name: The displayed identifier name of the system bot client.
        default_language: The fallback localization language code.
        bot_prefix: The designated text trigger pattern for executing the bot.
        environment: The current deployment context stage name.
    """

    model_config = ConfigDict(
        extra='allow',
    )

    bot_name: str = "p0x38's bot"
    default_language: str = 'en_US'
    bot_prefix: str = 'pox/'
    environment: str = 'dev'


class BotSettings(BaseSettings):
    """Centralize global application context settings and environment file processing.

    This class loads data from environmental variables using dual underscores as a
    nested delimiter structure to build sub-config models.

    Attributes:
        token_config: Parsed system API keys and platform tokens.
        database_config: Extracted settings for backend storage connections.
        trace_config: Configured values for telemetry and logging backends.
        logger: Configured thresholds for console and file log outputs.
        llm_config: Properties dictating current active model variants.
        bot_config: A specific bot configuration.
    """

    token_config: TokenConfig = Field(default_factory=TokenConfig)
    database_config: DatabaseConfig = Field(default_factory=DatabaseConfig)
    trace_config: TraceConfig = Field(default_factory=TraceConfig)
    logger: LoggerConfig = Field(default_factory=LoggerConfig)
    llm_config: LLMConfig = Field(default_factory=LLMConfig)
    piper_tts: PiperTTSConfig = Field(default_factory=PiperTTSConfig)
    bot_config: BotCustomConfig = Field(default_factory=BotCustomConfig)

    @computed_field
    @property
    def db_url(self) -> str:
        """Provide a property that extracts the complete database engine URL."""
        return self.database_config.build_url()

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            FlatAliasSettingsSource(settings_cls, env_settings),
            FlatAliasSettingsSource(settings_cls, dotenv_settings),
            file_secret_settings,
        )

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        env_nested_delimiter='__',
        extra='ignore',
    )
