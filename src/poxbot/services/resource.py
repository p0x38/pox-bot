from __future__ import annotations

import os
import pickle
from pathlib import Path
from typing import Any

import aiofiles
import orjson
from aiohttp import ClientSession
from profanityfilter import ProfanityFilter
from psutil import Process
from urlextract import URLExtract

from ..core.resources import (
    ResourceManager as ResourcePathManager,
    create_default_resource_manager,
)
from ..persistence.models.contributor import ContributorItem
from ..shared.utils import Cache


class ResourceManager:
    """Manage application resources and resource-related runtime services.

    This service keeps its existing convenience API while delegating all
    filesystem path resolution to the virtual resource manager.
    """

    def __init__(
        self,
        resource_manager: ResourcePathManager | None = None,
    ) -> None:
        self.session: ClientSession | None = None
        self.url_extrator = URLExtract()
        self.cache = Cache(60 * 60 * 24)
        self.pid = os.getpid()
        self.process = Process(self.pid)
        self.profanity_filter = ProfanityFilter()

        self.resource_paths = resource_manager or create_default_resource_manager()
        self.assets_path = self.resource_paths.get_root("assets")
        self.userdata_path = self.resource_paths.get_root("userdata")
        self.root_path = self.assets_path.parent

    async def initialize(self) -> None:
        self.session = ClientSession()
        self.userdata_path.mkdir(parents=True, exist_ok=True)

    async def close(self) -> None:
        if self.session is not None and not self.session.closed:
            await self.session.close()

    @staticmethod
    def _join_address_paths(*paths: str) -> str:
        if not paths:
            raise ValueError("At least one resource path component is required.")
        if any(not isinstance(path, str) for path in paths):
            raise TypeError("Resource path components must be strings.")
        return "/".join(paths)

    def get_asset_path(self, *paths: str) -> Path:
        relative_path = self._join_address_paths(*paths)
        target_path = self.resource_paths.resolve_path(
            f"assets:{relative_path}",
        )
        if not target_path.exists():
            raise FileNotFoundError(f"Asset not found at: {target_path}")
        return target_path

    async def get_asset_path_async(self, *paths: str) -> Path:
        return self.get_asset_path(*paths)

    def get_user_data_path(
        self,
        *paths: str,
        must_exist: bool = False,
    ) -> Path:
        relative_path = self._join_address_paths(*paths)
        target_path = self.resource_paths.resolve_path(
            f"userdata:{relative_path}",
        )
        if must_exist and not target_path.exists():
            raise FileNotFoundError(
                f"User-data resource not found at: {target_path}",
            )
        return target_path

    def _get_overlay_path(self, *paths: str) -> Path:
        user_data_path = self.get_user_data_path(*paths)
        if user_data_path.is_file():
            return user_data_path
        return self.get_asset_path(*paths)

    def load_json_asset(self, *paths: str) -> dict[str, Any] | list[Any]:
        file_path = self.get_asset_path(*paths)
        return orjson.loads(file_path.read_bytes())

    async def load_json_asset_async(
        self,
        *paths: str,
    ) -> dict[str, Any] | list[Any]:
        file_path = self.get_asset_path(*paths)

        async with aiofiles.open(file_path, "rb") as file:
            content = await file.read()

        return orjson.loads(content)

    def read_text_asset(self, *paths: str) -> str:
        return self.get_asset_path(*paths).read_text(encoding="utf-8")

    async def load_contributors_async(
        self,
        *paths: str,
    ) -> list[ContributorItem]:
        raw_data = await self.load_json_asset_async(*paths)

        if not isinstance(raw_data, list):
            raise ValueError(
                f"Expected a list of contributors, got {type(raw_data)}",
            )

        return [ContributorItem.model_validate(item) for item in raw_data]

    async def save_with_orjson_async(
        self,
        data: dict[str, Any] | list[Any],
        *paths: str,
    ) -> None:
        file_path = self.get_user_data_path(*paths)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path = self.resource_paths.resolve_path(
            f"userdata:{self._join_address_paths(*paths)}",
            write=True,
        )

        async with aiofiles.open(file_path, "wb") as file:
            await file.write(orjson.dumps(data))

    async def load_with_orjson_async(
        self,
        *paths: str,
    ) -> dict[str, Any] | list[Any]:
        file_path = self._get_overlay_path(*paths)

        async with aiofiles.open(file_path, "rb") as file:
            content = await file.read()

        return orjson.loads(content)

    async def save_with_pickle_async(self, data: Any, *paths: str) -> None:
        file_path = self.get_user_data_path(*paths)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path = self.resource_paths.resolve_path(
            f"userdata:{self._join_address_paths(*paths)}",
            write=True,
        )

        async with aiofiles.open(file_path, "wb") as file:
            await file.write(pickle.dumps(data))

    async def load_with_pickle_async(self, *paths: str) -> Any:
        file_path = self._get_overlay_path(*paths)

        async with aiofiles.open(file_path, "rb") as file:
            content = await file.read()

        return pickle.loads(content)
