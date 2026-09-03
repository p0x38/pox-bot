import logging
from logging import getLogger

from textual.widgets import RichLog

from ...config.schema import BotSettings
from .adapters import PrefixAdapter
from .handlers import setup_console_handler, setup_file_handler, setup_loki_handler

_configured = False


def configure_logging(settings: BotSettings, *, log_widget: RichLog | None = None):
    global _configured  # ruff: ignore[global-statement]

    logging.getLogger('urllib3').setLevel(logging.INFO)
    logging.getLogger('requests').setLevel(logging.INFO)
    logging.getLogger('logging_loki').setLevel(logging.INFO)
    logging.getLogger('discord').setLevel(logging.INFO)

    if _configured:
        return

    config = settings.logger
    level = getattr(logging, config.level.upper(), logging.INFO)

    root = getLogger()
    root.setLevel(level)
    root.handlers.clear()

    if settings.logger.enabled:
        if settings.logger.console_logging.enabled:
            setup_console_handler(root, level, settings, log_widget=log_widget)
        if settings.logger.file_logging.enabled:
            setup_file_handler(root, level, settings)
    if settings.trace_config.enabled:
        setup_loki_handler(root, level, settings)

    _configured = True


def get_logger(name: str, *, prefix: str | None = None, extension: str | None = None):
    extra = {'prefix': prefix, 'extension': extension}
    return PrefixAdapter(getLogger(name), extra)
