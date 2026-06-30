from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class DatabaseConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 5432
    user: str = "postgres"
    password: SecretStr = SecretStr("postgres")
    name: str = "postgres"
    driver: str = "postgresql+asyncpg"

    def build_url(self) -> str:
        """Generates Data Source Name (DSN) for SQLAlchemy.

        Returns DSN as a string to ensure compatibility with the asynchronous engine.

        Returns:
            str: a DSN string to connect.
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
    enabled: bool = True
    directory: Path = Field(default=Path("logs/"))
    encoding: str = "utf-8"


class ConsoleLoggingConfig(BaseModel):
    rich_tracebacks: bool = True
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    markup: bool = True


class LoggerConfig(BaseModel):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "DEBUG"
    file_logging: FileLoggingConfig = Field(default_factory=FileLoggingConfig)
    console_logging: ConsoleLoggingConfig = Field(default_factory=ConsoleLoggingConfig)


class TokenConfig(BaseModel):
    discord_token: SecretStr = SecretStr("")
    lmstudio_token: SecretStr = SecretStr("")
    openai_api_key: SecretStr = SecretStr("")
    openrouter_api_key: SecretStr = SecretStr("")


class TraceConfig(BaseModel):
    enabled: bool = True
    opentelemetry_endpoint: str = "http://localhost:4317"
    prometheus_server_port: int = 8001
    insecure: bool = True
    sampling_ratio: float = Field(default=1.0, ge=0.0, le=1.0)
    export_interval_ms: int = 1000 * 15
    max_batch_size: int = 512


class LLMConfig(BaseModel):
    model_id: str = ""


class BotSettings(BaseSettings):
    token_config: TokenConfig = Field(default_factory=TokenConfig)
    database_config: DatabaseConfig = Field(default_factory=DatabaseConfig)
    trace_config: TraceConfig = Field(default_factory=TraceConfig)
    logger: LoggerConfig = Field(default_factory=LoggerConfig)
    llm_config: LLMConfig = Field(default_factory=LLMConfig)
    
    bot_name: str = "TehBot"
    default_language: str = "en"
    bot_prefix: str = "pox/"

    @computed_field
    @property
    def db_url(self) -> str:
        return self.database_config.build_url()

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )
