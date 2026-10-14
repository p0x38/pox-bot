from __future__ import annotations

import os
from pathlib import Path

from discord import Intents
from discord.ext import commands
from dotenv import load_dotenv

from .application import PoxBot
from .application.context import ApplicationContext
from .config.manager import ConfigManager
from .core.resources import FilesystemResolver, ResourceManager
from .infrastructure.logger import configure_logging, get_logger
from .infrastructure.textual_dashboard import TextualDashboard
from .infrastructure.web.api_manager import FastAPIManager
from .services.i18n import I18nManager


class Bootstrap:
    def __init__(self, *, show_textual: bool = False):
        load_dotenv()
        self.show_textual = show_textual
        self._context: ApplicationContext | None = None

    async def create_context(self) -> ApplicationContext:
        if self._context is not None:
            return self._context

        custom_config_path = os.environ.get('POXBOT_CONFIG_PATH')

        settings = await ConfigManager.get_settings(
            path=Path(custom_config_path) if custom_config_path else None,
        )
        dashboard = TextualDashboard() if self.show_textual else None

        configure_logging(
            settings, log_widget=dashboard.log_widget if dashboard is not None else None
        )

        system_logger = get_logger(__name__, prefix='System')

        package_dir = Path(__file__).resolve().parent  # ruff: ignore[blocking-path-method-in-async-function]
        resource_manager = ResourceManager()
        resource_manager.register(
            'assets',
            FilesystemResolver(package_dir / 'assets'),
        )
        resource_manager.register(
            'extensions',
            FilesystemResolver(package_dir.parent),
        )
        i18n = I18nManager(
            locales_path=resource_manager.resolve_path('assets:locales'),
            resource_manager=resource_manager,
        )

        root = Path(__file__).resolve()  # ruff: ignore[blocking-path-method-in-async-function]

        fastapi_class = FastAPIManager(host='0.0.0.0', port=8000)

        self._context = ApplicationContext(
            settings=settings,
            logger=system_logger,
            root_path=root.parent.parent,
            i18n=i18n,
            resource_manager=resource_manager,
            fastapi_class=fastapi_class,
            dashboard=dashboard,
        )
        return self._context

    async def create_bot(self) -> PoxBot:
        context = await self.create_context()

        return PoxBot(
            context=context,
            intents=Intents.all(),
            command_prefix=commands.when_mentioned_or(
                context.settings.bot_config.bot_prefix
            ),
        )

    @property
    def context(self) -> ApplicationContext:
        if self._context is None:
            raise RuntimeError('Context has not been created yet.')
        return self._context

    @property
    def token(self) -> str:
        token = self.context.settings.token_config.discord_token
        return token.get_secret_value().strip()
