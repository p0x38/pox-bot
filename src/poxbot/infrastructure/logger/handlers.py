from __future__ import annotations

import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import logging_loki
from rich.console import Console
from rich.logging import RichHandler

from ...config.schema import BotSettings
from .filters import ExcludeConsoleFilter, SkipEmptyMessageFilter
from .formatters import JSONFormatter

console = Console()


def setup_console_handler(root: logging.Logger, level: int, settings: BotSettings) -> None:
    handler = RichHandler(
        console=console,
        show_time=True,
        rich_tracebacks=settings.logger.console_logging.rich_tracebacks,
        markup=settings.logger.console_logging.markup,
        level=level,
    )
    handler.addFilter(ExcludeConsoleFilter())
    handler.addFilter(SkipEmptyMessageFilter())

    root.addHandler(handler)


def setup_file_handler(
    root: logging.Logger, level: int, settings: BotSettings,
) -> None:
    if not settings.logger.file_logging.enabled:
        return

    log_dir = Path(settings.logger.file_logging.directory)
    log_dir.mkdir(exist_ok=True)

    handler = TimedRotatingFileHandler(
        str(log_dir / "main.log"),
        when='d',
        backupCount=365,
        encoding=settings.logger.file_logging.encoding,
    )

    handler.setLevel(level)
    handler.setFormatter(JSONFormatter())

    root.addHandler(handler)


def setup_loki_handler(
    root: logging.Logger, level: int, settings: BotSettings,
) -> None:
    trace_cfg = getattr(settings, 'trace_config', None)

    if not trace_cfg or not trace_cfg.enabled:
        return

    if not trace_cfg.loki_url:
        return

    handler = logging_loki.LokiHandler(
        url=trace_cfg.loki_url,
        tags={
            'application': 'bot',
            'environment': getattr(settings, 'environment', 'production'),
        },
        version='1',
    )
    handler.setLevel(level)
    handler.setFormatter(JSONFormatter())
    root.addHandler(handler)
