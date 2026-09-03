from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

from ..shared.utils.app_path import app_dir


class DatabaseConfig(BaseModel):
    """Represent configuration parameters required to establish a database connection.

    This Pydantic model holds the database connection settings, including credentials,
    host parameters, and the backend driver specifications.

    Attributes:
        host (str): The IP address or hostname of the database server.
        port (int): The port number on which the database server is listening.
        user (str): The username utilized for database authentication.
        password (SecretStr): The sensitive password wrapper for authentication.
        name (str): The name of the target database instance.
        driver (str): The specific SQLAlchemy dialect and async driver combination.
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
        enabled (bool): Toggle status to control whether file logging is active.
        directory (Path): The destination file path directory where logs are stored.
        encoding (str): The text encoding method applied to generated log files.
    """

    enabled: bool = True
    directory: Path = Field(default=app_dir.user_log_path)
    encoding: str = 'utf-8'


class ConsoleLoggingConfig(BaseModel):
    """Define configuration metrics for terminal-based log presentation.

    Attributes:
        enabled (bool): The toggle for visibility to show/hide logs.
        rich_tracebacks (bool): Toggle status to enable advanced terminal tracebacks.
        level (str): The threshold logging level for standard output.
        markup (bool): Toggle status to support inline console formatting tags.
    """

    enabled: bool = True
    rich_tracebacks: bool = True
    level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] = 'INFO'
    markup: bool = True


class LoggerConfig(BaseModel):
    """Manage systemic logging behavior across console and file channels.

    Attributes:
        enabled (bool): The toggle for visibility to enable logging.
        level (str): The root logging severity for the application.
        file_logging (FileLoggingConfig): Dedicated settings for file log output.
        console_logging (ConsoleLoggingConfig): Dedicated settings for console log
            output.
    """

    enabled: bool = True
    level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] = 'DEBUG'
    file_logging: FileLoggingConfig = Field(default_factory=FileLoggingConfig)
    console_logging: ConsoleLoggingConfig = Field(default_factory=ConsoleLoggingConfig)


class TokenConfig(BaseModel):
    """Store critical integration tokens and authorization keys securely.

    Attributes:
        discord_token (SecretStr): Protected API token for the Discord bot client.
        lmstudio_token (SecretStr): Protected access key for local LM-Studio instances.
        openai_api_key (SecretStr): Protected developer key for OpenAI endpoints.
        openrouter_api_key (SecretStr): Protected provider key for OpenRouter routing.
    """

    discord_token: SecretStr = SecretStr('')
    lmstudio_token: SecretStr = SecretStr('')
    openai_api_key: SecretStr = SecretStr('')
    openrouter_api_key: SecretStr = SecretStr('')


class TraceConfig(BaseModel):
    """Govern OpenTelemetry tracing, metric collection, and observability.

    Attributes:
        enabled (bool): Toggle status to activate or disable system telemetry tracking.
        opentelemetry_endpoint (str): Base destination URI for OTLP collectors.
        otlp_traces_endpoint (str | None): Explicit endpoint target for processing
            traces.
        otlp_metrics_endpoint (str | None): Explicit endpoint for collecting metrics.
        loki_url (str): Target endpoint for dispatching collected logs to Grafana Loki.
        prometheus_host (str): The local network interface address for Prometheus
            metrics.
        prometheus_server_port (int): The local port assigned to the Prometheus metrics
            server.
        insecure (bool): Toggle status to bypass TLS validation for telemetry endpoints.
        sampling_ratio (float): The target proportion of requests to trace.
        export_interval_ms (int): The frequency delay between batch data exports.
        max_batch_size (int): The maximum buffer volume of items sent per export cycle.
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
        provider_type (str): The configured LLM provider identifier.
        model_id (str): The identifier tag of the targeted model variant.
    """

    provider_type: Literal['openrouter', 'ollama', 'gemini', 'openai'] = 'openrouter'
    model_id: str = ''


class BotSettings(BaseSettings):
    """Centralize global application context settings and environment file processing.

    This class loads data from environmental variables using dual underscores as a
    nested delimiter structure to build sub-config models.

    Attributes:
        token_config (TokenConfig): Parsed system API keys and platform tokens.
        database_config (DatabaseConfig): Extracted settings for backend storage
            connections.
        trace_config (TraceConfig): Configured values for telemetry and logging
            backends.
        logger (LoggerConfig): Configured thresholds for console and file log outputs.
        llm_config (LLMConfig): Properties dictating current active model variants.
        bot_name (str): The displayed identifier name of the system bot client.
        default_language (str): The fallback localization language code.
        bot_prefix (str): The designated text trigger pattern for executing the bot.
        environment (str): The current deployment context stage name.
    """

    token_config: TokenConfig = Field(default_factory=TokenConfig)
    database_config: DatabaseConfig = Field(default_factory=DatabaseConfig)
    trace_config: TraceConfig = Field(default_factory=TraceConfig)
    logger: LoggerConfig = Field(default_factory=LoggerConfig)
    llm_config: LLMConfig = Field(default_factory=LLMConfig)

    bot_name: str = 'TehBot'
    default_language: str = 'en'
    bot_prefix: str = 'pox/'
    environment: str = 'development'

    @computed_field
    @property
    def db_url(self) -> str:
        """Provide a property that extracts the complete database engine URL."""
        return self.database_config.build_url()

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        env_nested_delimiter='__',
        extra='ignore',
    )
