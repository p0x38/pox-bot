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


class ConfigModel(BaseModel):
    model_config = ConfigDict(validate_by_name=True)


class PiperTTSConfig(ConfigModel):
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

    default_voice: str = Field(
        default='en_US-john-medium',
        validation_alias='POXBOT_PIPER_DEFAULT_VOICE',
    )

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
        validation_alias='POXBOT_PIPER_ALLOWED_VOICES',
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


class DatabaseConfig(ConfigModel):
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

    host: str = Field(
        default='127.0.0.1',
        validation_alias='POXBOT_DATABASE_HOST',
    )

    port: int = Field(
        default=5432,
        validation_alias='POXBOT_DATABASE_PORT',
    )

    user: str = Field(
        default='postgres',
        validation_alias='POXBOT_DATABASE_USER',
    )

    password: SecretStr = Field(
        default=SecretStr('postgres'),
        validation_alias='POXBOT_DATABASE_PASSWORD',
    )

    name: str = Field(
        default='postgres',
        validation_alias='POXBOT_DATABASE_NAME',
    )

    driver: str = Field(
        default='postgresql+asyncpg',
        validation_alias='POXBOT_DATABASE_DRIVER',
    )

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


class FileLoggingConfig(ConfigModel):
    """Define configuration settings for exporting logs directly to file storage.

    Attributes:
        enabled: Toggle status to control whether file logging is active.
        directory: The destination file path directory where logs are stored.
        encoding: The text encoding method applied to generated log files.
    """

    enabled: bool = Field(
        default=True,
        validation_alias='POXBOT_LOG_FILE_ENABLED',
    )

    directory: Path = Field(
        default=app_dir.user_log_path,
        validation_alias='POXBOT_LOG_FILE_DIRECTORY',
    )

    encoding: str = Field(
        default='utf-8',
        validation_alias='POXBOT_LOG_FILE_ENCODING',
    )


class ConsoleLoggingConfig(ConfigModel):
    """Define configuration metrics for terminal-based log presentation.

    Attributes:
        enabled: The toggle for visibility to show/hide logs.
        rich_tracebacks: Toggle status to enable advanced terminal tracebacks.
        level: The threshold logging level for standard output.
        markup: Toggle status to support inline console formatting tags.
    """

    enabled: bool = Field(
        default=True,
        validation_alias='POXBOT_LOG_CONSOLE_ENABLED',
    )

    rich_tracebacks: bool = Field(
        default=True,
        validation_alias='POXBOT_LOG_CONSOLE_RICH_TRACEBACKS',
    )

    level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] = Field(
        default='INFO',
        validation_alias='POXBOT_LOG_CONSOLE_LEVEL',
    )

    markup: bool = Field(
        default=True,
        validation_alias='POXBOT_LOG_CONSOLE_MARKUP',
    )


class LoggerConfig(ConfigModel):
    """Manage systemic logging behavior across console and file channels.

    Attributes:
        enabled: The toggle for visibility to enable logging.
        level: The root logging severity for the application.
        file_logging: Dedicated settings for file log output.
        console_logging: Dedicated settings for console log output.
    """

    enabled: bool = Field(
        default=True,
        validation_alias='POXBOT_LOG_ENABLED',
    )

    level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] = Field(
        default='DEBUG',
        validation_alias='POXBOT_LOG_LEVEL',
    )

    file_logging: FileLoggingConfig = Field(
        default_factory=FileLoggingConfig,
    )

    console_logging: ConsoleLoggingConfig = Field(
        default_factory=ConsoleLoggingConfig,
    )


class TokenConfig(ConfigModel):
    """Store critical integration tokens and authorization keys securely.

    Attributes:
        discord_token: Protected API token for the Discord bot client.
        lmstudio_token: Protected access key for local LM-Studio instances.
        openai_api_key: Protected developer key for OpenAI endpoints.
        openrouter_api_key: Protected provider key for OpenRouter routing.
    """

    discord_token: SecretStr = Field(
        default=SecretStr(''),
        validation_alias='POXBOT_DISCORD_TOKEN',
    )

    lmstudio_token: SecretStr = Field(
        default=SecretStr(''),
        validation_alias='POXBOT_LMSTUDIO_TOKEN',
    )

    openai_api_key: SecretStr = Field(
        default=SecretStr(''),
        validation_alias='POXBOT_OPENAI_API_KEY',
    )

    openrouter_api_key: SecretStr = Field(
        default=SecretStr(''),
        validation_alias='POXBOT_OPENROUTER_API_KEY',
    )


class TraceConfig(ConfigModel):
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

    enabled: bool = Field(
        default=True,
        validation_alias='POXBOT_TRACE_ENABLED',
    )

    opentelemetry_endpoint: str = Field(
        default='http://127.0.0.1:4317',
        validation_alias='POXBOT_TRACE_OPENTELEMETRY_ENDPOINT',
    )

    otlp_traces_endpoint: str | None = Field(
        default=None,
        validation_alias='POXBOT_TRACE_OTLP_TRACES_ENDPOINT',
    )

    otlp_metrics_endpoint: str | None = Field(
        default=None,
        validation_alias='POXBOT_TRACE_OTLP_METRICS_ENDPOINT',
    )

    loki_url: str = Field(
        default='http://127.0.0.1:3100/loki/api/v1/push',
        validation_alias='POXBOT_TRACE_LOKI_URL',
    )

    prometheus_host: str = Field(
        default='0.0.0.0',
        validation_alias='POXBOT_TRACE_PROMETHEUS_HOST',
    )

    prometheus_server_port: int = Field(
        default=8001,
        validation_alias='POXBOT_TRACE_PROMETHEUS_SERVER_PORT',
    )

    insecure: bool = Field(
        default=True,
        validation_alias='POXBOT_TRACE_INSECURE',
    )

    sampling_ratio: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        validation_alias='POXBOT_TRACE_SAMPLING_RATIO',
    )

    export_interval_ms: int = Field(
        default=1000 * 15,
        validation_alias='POXBOT_TRACE_EXPORT_INTERVAL_MS',
    )

    max_batch_size: int = Field(
        default=512,
        validation_alias='POXBOT_TRACE_MAX_BATCH_SIZE',
    )


class LLMConfig(ConfigModel):
    """Represent setting parameters allocated for language model behaviors.

    Attributes:
        provider_type: The configured LLM provider identifier.
        model_id: The identifier tag of the targeted model variant.
    """

    provider_type: Literal['openrouter', 'ollama', 'gemini', 'openai'] = Field(
        default='openrouter',
        validation_alias='POXBOT_LLM_PROVIDER',
    )

    model_id: str = Field(
        default='',
        validation_alias='POXBOT_LLM_MODEL',
    )


class BotCustomConfig(ConfigModel):
    """A config model for bot itself.

    Attributes:
        bot_name: The displayed identifier name of the system bot client.
        default_language: The fallback localization language code.
        bot_prefix: The designated text trigger pattern for executing the bot.
        environment: The current deployment context stage name.
    """

    model_config = ConfigDict(
        extra='allow',
        validate_by_name=True,
    )

    bot_name: str = Field(
        default="p0x38's bot",
        validation_alias='POXBOT_BOT_NAME',
    )

    default_language: str = Field(
        default='en_US',
        validation_alias='POXBOT_DEFAULT_LANGUAGE',
    )

    bot_prefix: str = Field(
        default='pox/',
        validation_alias='POXBOT_BOT_PREFIX',
    )

    environment: str = Field(
        default='dev',
        validation_alias='POXBOT_ENVIRONMENT',
    )


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
            FlatAliasSettingsSource(settings_cls, env_settings),
            FlatAliasSettingsSource(settings_cls, dotenv_settings),
            init_settings,
            file_secret_settings,
        )

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        env_nested_delimiter='__',
        extra='ignore',
    )
