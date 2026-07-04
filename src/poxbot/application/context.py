from __future__ import annotations

from dataclasses import dataclass
from logging import Logger, LoggerAdapter
from pathlib import Path as StdPath

from anyio import Path as AsyncPath

from ..config.schema import BotSettings
from ..infrastructure.web.api_manager import FastAPIManager
from ..services.i18n import I18nManager


@dataclass(slots=True, frozen=True)
class ApplicationContext:
    settings: BotSettings
    
    logger: LoggerAdapter | Logger
    bot_logger: LoggerAdapter | Logger
    
    root_path: StdPath | AsyncPath
    
    i18n: I18nManager
    fastapi_class: FastAPIManager
