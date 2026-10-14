import asyncio
from pathlib import Path

import aiofiles
import orjson
from pydantic import ValidationError

from ..shared.utils.app_path import app_dir
from .schema import BotSettings


class ConfigManager:
    """Manages the application configuration file lifecycle.

    Handles asynchronous loading, parsing, validation, and saving of
    the BotSettings schema using atomic file operations.

    Attributes:
        path: The absolute target path to the configuration file.
        settings: The current validated in-memory settings instance.
    """

    def __init__(self, path: Path | None = None):
        """Initialize the ConfigManager and resolves its file path.

        Args:
            path: Custom path to the config file. Defaults to None.
        """
        self._uses_default_path = path is None
        self._bundled_path = (
            Path(__file__).resolve().parent.parent / 'assets' / 'config.json'
        )
        self.path = self._resolve_path(path)
        self.settings = BotSettings()

    def _resolve_path(self, path: Path | None = None) -> Path:
        """Resolve a given path or provides the default fallback path.

        Args:
            path: The path to resolve. Defaults to None.

        Returns:
            Path: An absolute path pointing to the configuration script.
        """
        if path is None:
            path = app_dir.user_data_path / 'config.json'

        return path.expanduser().resolve()

    async def _load_settings(self, path: Path) -> BotSettings:
        """Read and validates configuration data from the filesystem.

        Args:
            path: The absolute path to read from

        Returns:
            BotSettings: The validated settings instance.

        Raises:
            RuntimeError: If JSON decoding or Pydantic validation fails.
        """
        try:
            async with aiofiles.open(path, 'rb') as f:
                content = await f.read()

            data = await asyncio.to_thread(orjson.loads, content)
            return BotSettings.model_validate(data)

        except FileNotFoundError:
            return BotSettings()
        except orjson.JSONDecodeError as e:
            raise RuntimeError(f'Config file contains invalid JSON: {e}') from e
        except ValidationError as e:
            raise RuntimeError(f'Config validation constraints failed: {e}') from e

    async def load(self) -> BotSettings:
        """Load and updates the internal settings state from disk.

        Returns:
            BotSettings: The newly updated internal settings state.
        """
        if self.path.exists():
            self.settings = await self._load_settings(self.path)
        elif self._uses_default_path:
            self.settings = await self._load_settings(self._bundled_path)
        else:
            self.settings = BotSettings()

        return self.settings

    async def save(self) -> None:
        """Serialize and writes the internal settings state back to disk.

        Automatically creates missing parent directories if necessary.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)

        data = self.settings.model_dump()

        content = await asyncio.to_thread(
            orjson.dumps,
            data,
            option=orjson.OPT_INDENT_2,
        )

        async with aiofiles.open(self.path, 'wb') as f:
            await f.write(content)

    async def reload(self) -> BotSettings:
        """Reload configuration parameters from disk to refresh local state.

        Returns:
            BotSettings: The reloaded application configuration.
        """
        return await self.load()

    @classmethod
    async def get_settings(cls, path: Path | None = None) -> BotSettings:
        """Classmethod to setup manager initialization and loader at once.

        Args:
            path: Path to setup. Defaults to None.

        Returns:
            BotSettings: Validated BotSettings.
        """
        instance = cls(path)
        return await instance.load()
