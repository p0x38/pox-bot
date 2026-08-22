from __future__ import annotations

import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING

import logging_loki
from rich.console import Console
from rich.logging import RichHandler

from ...config.schema import BotSettings
from .filters import ExcludeConsoleFilter, SkipEmptyMessageFilter
from .formatters import JSONFormatter

if TYPE_CHECKING:
    from textual.widgets import RichLog

console = Console()


class TextualRichHandler(RichHandler):
    def __init__(self, log_widget: RichLog, console: Console, *args, **kwargs) -> None:
        super().__init__(console=console, *args, **kwargs)
        self.log_widget = log_widget

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
            message_renderable = self.render_message(record, message)
            traceback = None
            renderables = self.render(
                record=record,
                traceback=traceback,
                message_renderable=message_renderable,
            )
            self.log_widget.write(renderables)
        except Exception:
            self.handleError(record)


def setup_console_handler(
    root: logging.Logger,
    level: int,
    settings: BotSettings,
    log_widget: RichLog | None = None,
) -> None:
    target_console = (
        Console(force_terminal=True, color_system='truecolor')
        if log_widget
        else console
    )

    handler_kwargs = {
        'console': target_console,
        'show_time': True,
        'rich_tracebacks': settings.logger.console_logging.rich_tracebacks,
        'markup': settings.logger.console_logging.markup,
        'level': level,
    }

    if log_widget is not None:
        handler: logging.Handler = TextualRichHandler(
            log_widget=log_widget, **handler_kwargs,
        )
    else:
        handler = RichHandler(**handler_kwargs)

    handler.addFilter(ExcludeConsoleFilter())
    handler.addFilter(SkipEmptyMessageFilter())

    root.addHandler(handler)


def setup_file_handler(
    root: logging.Logger,
    level: int,
    settings: BotSettings,
) -> None:
    if not settings.logger.file_logging.enabled:
        return

    log_dir = Path(settings.logger.file_logging.directory)
    log_dir.mkdir(exist_ok=True)

    handler = TimedRotatingFileHandler(
        str(log_dir / 'main.log'),
        when='d',
        backupCount=365,
        encoding=settings.logger.file_logging.encoding,
    )

    handler.setLevel(level)
    handler.setFormatter(JSONFormatter())

    root.addHandler(handler)


def setup_loki_handler(
    root: logging.Logger,
    level: int,
    settings: BotSettings,
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
