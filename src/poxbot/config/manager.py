import asyncio
from pathlib import Path

import aiofiles
import orjson
from pydantic import ValidationError

from ..core.resources import (
    ResourceManager as ResourcePathManager,
    create_default_resource_manager,
)
from .schema import BotSettings


class ConfigManager:
    """Manage configuration loading, validation, and persistence."""

    RESOURCE_ADDRESS = "userdata:config.json"
    LEGACY_RESOURCE_ADDRESS = "assets:config.json"

    def __init__(
        self,
        path: Path | None = None,
        *,
        resource_manager: ResourcePathManager | None = None,
    ):
        self.resource_manager = resource_manager or create_default_resource_manager()
        self._uses_resource_address = path is None
        self.path = (
            self.resource_manager.resolve_path(self.RESOURCE_ADDRESS)
            if path is None
            else self._resolve_path(path)
        )
        self.settings = BotSettings()

    def _resolve_path(self, path: Path | None = None) -> Path:
        if path is None:
            return self.resource_manager.resolve_path(self.RESOURCE_ADDRESS)
        return Path(path).expanduser().resolve()

    async def _load_settings(self, path: Path) -> BotSettings:
        try:
            async with aiofiles.open(path, "rb") as file:
                content = await file.read()

            data = await asyncio.to_thread(orjson.loads, content)
            return BotSettings.model_validate(data)

        except FileNotFoundError:
            return BotSettings()
        except orjson.JSONDecodeError as exc:
            raise RuntimeError(f"Config file contains invalid JSON: {exc}") from exc
        except ValidationError as exc:
            raise RuntimeError(
                f"Config validation constraints failed: {exc}",
            ) from exc

    async def load(self) -> BotSettings:
        source_path = self.path

        if self._uses_resource_address and not source_path.is_file():
            legacy_path = self.resource_manager.resolve_path(
                self.LEGACY_RESOURCE_ADDRESS,
            )
            if legacy_path.is_file():
                source_path = legacy_path

        self.settings = await self._load_settings(source_path)
        return self.settings

    async def save(self) -> None:
        if self._uses_resource_address:
            self.path = self.resource_manager.resolve_path(
                self.RESOURCE_ADDRESS,
                write=True,
            )
        self.path.parent.mkdir(parents=True, exist_ok=True)

        if self._uses_resource_address:
            self.path = self.resource_manager.resolve_path(
                self.RESOURCE_ADDRESS,
                write=True,
            )

        content = await asyncio.to_thread(
            orjson.dumps,
            self.settings.model_dump(),
            option=orjson.OPT_INDENT_2,
        )

        async with aiofiles.open(self.path, "wb") as file:
            await file.write(content)

    async def reload(self) -> BotSettings:
        return await self.load()

    @classmethod
    async def get_settings(
        cls,
        path: Path | None = None,
        *,
        resource_manager: ResourcePathManager | None = None,
    ) -> BotSettings:
        instance = cls(path, resource_manager=resource_manager)
        return await instance.load()
