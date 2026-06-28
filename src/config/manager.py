import asyncio
from pathlib import Path

import aiofiles
import orjson
from pydantic import ValidationError

from .schema import BotSettings


class ConfigManager:
    """Manages the application configuration file lifecycle.

    Handles asynchronous loading, parsing, validation, and saving of
    the BotSettings schema using atomic file operations.

    Attributes:
        path (Path): The absolute target path to the configuration file.
        settings (BotSettings): The current validated in-memory settings instance.
    """
    def __init__(self, path: Path | None = None):
        """Initializes the ConfigManager and resolves its file path.

        Args:
            path (Path, optional): Custom path to the config file. Defaults to None.
        """
        self.path = self._resolve_path(path)
        self.settings = BotSettings()

    def _resolve_path(self, path: Path | None = None) -> Path:
        """Resolves a given path or provides the default fallback path.

        Args:
            path (Path, optional): The path to resolve. Defaults to None.

        Returns:
            Path: An absolute path pointing to the configuration script.
        """
        if path is None:
            path = Path(__file__).resolve().parent.parent / "assets" / "config.json"

        return path.resolve()

    async def _load_settings(self, path: Path) -> BotSettings:
        """Reads and validates configuration data from the filesystem.

        Args:
            path (Path): The absolute path to read from

        Raises:
            RuntimeError: If JSON decoding or Pydantic validation fails.

        Returns:
            BotSettings: The validated settings instance.
        """
        try:
            async with aiofiles.open(path, "rb") as f:
                content = await f.read()

            data = await asyncio.to_thread(orjson.loads, content)
            return BotSettings.model_validate(data)

        except FileNotFoundError:
            return BotSettings()
        except orjson.JSONDecodeError as e:
            raise RuntimeError(f"Config file contains invalid JSON: {e}") from e
        except ValidationError as e:
            raise RuntimeError(f"Config validation constraints failed: {e}") from e

    async def load(self) -> BotSettings:
        """Loads and updates the internal settings state from disk.

        Returns:
            BotSettings: The newly updated internal settings state.
        """
        self.settings = await self._load_settings(self.path)
        return self.settings

    async def save(self) -> None:
        """Serializes and writes the internal settings state back to disk.

        Automatically creates missing parent directories if necessary.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)

        data = self.settings.model_dump()

        content = await asyncio.to_thread(
            orjson.dumps,
            data,
            option=orjson.OPT_INDENT_2,
        )

        async with aiofiles.open(self.path, "wb") as f:
            await f.write(content)

    async def reload(self) -> BotSettings:
        """Reloads configuration parameters from disk to refresh local state.

        Returns:
            BotSettings: The reloaded application configuration.
        """
        return await self.load()

    @classmethod
    async def get_settings(cls, path: Path | None = None) -> BotSettings:
        """A classmethod to setup manager initialization and loader at once.

        Args:
            path (Path, optional): Path to setup. Defaults to None.

        Returns:
            BotSettings: Validated BotSettings.
        """
        instance = cls(path)
        return await instance.load()
