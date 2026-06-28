import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class DatabaseConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 5432
    user: str = "postgres"
    password: str = "postgres"
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
            password=self.password,
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
    markup: bool = True


class LoggerConfig(BaseModel):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    file_logging: FileLoggingConfig = Field(default_factory=FileLoggingConfig)
    console_logging: ConsoleLoggingConfig = Field(default_factory=ConsoleLoggingConfig)


class TokenConfig(BaseModel):
    discord_token: str = ""
    lmstudio_token: str = ""
    openai_api_key: str = ""
    openrouter_api_key: str = ""


class BotSettings(BaseSettings):
    token_config: TokenConfig = Field(default_factory=TokenConfig)
    database_config: DatabaseConfig = Field(default_factory=DatabaseConfig)

    bot_name: str = "TehBot"
    default_language: str = "en"
    bot_prefix: str = "pox/"

    logger: LoggerConfig = Field(default_factory=LoggerConfig)

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
