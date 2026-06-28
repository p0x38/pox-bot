import logging
import os
from logging import Formatter, LoggerAdapter, getLogger
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import orjson
from rich.console import Console
from rich.logging import RichHandler

from src.config.schema import LoggerConfig

console = Console()

BASE_PATH = Path(__file__).resolve().parent


class PrefixAdapter(LoggerAdapter):
    def process(self, msg, kwargs):
        if self.extra and self.extra.get("prefix"):
            return f"[{self.extra['prefix']}] {msg}", kwargs
        return msg, kwargs


def load_log_config() -> LoggerConfig:
    config_path = BASE_PATH / ".." / "assets" / "logger.json"

    try:
        with open(config_path, encoding="utf-8") as f:
            data = orjson.loads(f.read())
            return LoggerConfig.model_validate(data)
    except FileNotFoundError:
        return LoggerConfig()
    except orjson.JSONDecodeError as e:
        print(f"Invalid JSON in logger_config.json: {e}")
        return LoggerConfig()
    except OSError as e:
        print(f"OS Error: {e}")
        return LoggerConfig()


def setup_logger(name: str = "pox-bot", prefix: str | None = None) -> LoggerAdapter:
    config = load_log_config()

    logger = getLogger(name)
    level = getattr(logging, config.level, logging.INFO)
    logger.setLevel(level)

    if logger.handlers:
        logger.handlers.clear()

    rich_handler = RichHandler(
        rich_tracebacks=config.console_logging.rich_tracebacks,
        markup=config.console_logging.markup,
        console=console,
        show_time=True,
    )
    logger.addHandler(rich_handler)

    if config.file_logging.enabled:
        log_dir = Path(config.file_logging.directory)
        os.makedirs(log_dir, exist_ok=True)

        file_path = log_dir / "main.log"

        file_handler = TimedRotatingFileHandler(
            str(file_path),
            encoding=config.file_logging.encoding,
            when="d",
            backupCount=365
        )

        file_handler.setFormatter(
            Formatter(fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )

        logger.addHandler(file_handler)

    return PrefixAdapter(logger, {"prefix": prefix})
