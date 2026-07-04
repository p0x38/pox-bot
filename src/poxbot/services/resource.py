import os
import pickle
from pathlib import Path
from typing import Any

import aiofiles
import orjson
from aiohttp import ClientSession
from gtts.lang import tts_langs
from profanityfilter import ProfanityFilter
from psutil import Process
from roblox import Client as RbxClient
from urlextract import URLExtract

from ..persistence.models.contributor import ContributorItem
from ..shared.utils import Cache


class ResourceManager:
    def __init__(self):
        self.session: ClientSession | None = None
        self.roblox_client = RbxClient()

        self.url_extrator = URLExtract()
        self.cache = Cache(60 * 60 * 24)

        self.gtts_cache_langs = tts_langs()

        self.pid = os.getpid()
        self.process = Process(self.pid)

        self.profanity_filter = ProfanityFilter()

        self.root_path = Path(__file__).resolve().parent.parent
        self.assets_path = self.root_path / 'assets'

    async def initialize(self):
        self.session = ClientSession()

        if not self.assets_path.exists():
            self.assets_path.mkdir(parents=True, exist_ok=True)

    async def close(self):
        if self.session:
            await self.session.close()

    def get_asset_path(self, *paths: str) -> Path:
        target_path = self.assets_path.joinpath(*paths)
        if not target_path.exists():
            raise FileNotFoundError(f'Asset not found at: {target_path}')
        return target_path

    def load_json_asset(self, *paths: str) -> dict[str, Any]:
        file_path = self.get_asset_path(*paths)

        with Path(file_path).open(encoding='utf-8') as f:
            return orjson.loads(f.read())

    async def load_json_asset_async(self, *paths: str) -> dict[str, Any] | list[Any]:
        file_path = self.get_asset_path(*paths)

        async with aiofiles.open(file_path, encoding='utf-8') as f:
            content = await f.read()
            return orjson.loads(content)

    def read_text_asset(self, *paths: str) -> str:
        file_path = self.get_asset_path(*paths)
        return file_path.read_text(encoding='utf-8')

    async def load_contributors_async(self, *paths: str) -> list[ContributorItem]:
        raw_data = await self.load_json_asset_async(*paths)

        if not isinstance(raw_data, list):
            raise ValueError(f'Expected a list of contributors, got {type(raw_data)}')

        return [ContributorItem.model_validate(item) for item in raw_data]

    async def save_with_orjson_async(
        self, data: dict[str, Any] | list[Any], *paths: str,
    ):
        file_path = self.assets_path.joinpath(*paths)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        binary_data = orjson.dumps(data)
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(binary_data)

    async def load_with_orjson_async(self, *paths: str) -> dict[str, Any] | list[Any]:
        file_path = self.get_asset_path(*paths)

        async with aiofiles.open(file_path, 'rb') as f:
            binary_content = await f.read()

        return orjson.loads(binary_content)

    async def save_with_pickle_async(self, data: Any, *paths: str):
        file_path = self.assets_path.joinpath(*paths)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        binary_data = pickle.dumps(data)

        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(binary_data)

    async def load_with_pickle_async(self, *paths: str) -> Any:
        file_path = self.get_asset_path(*paths)

        async with aiofiles.open(file_path, 'rb') as f:
            binary_content = await f.read()

        return pickle.loads(binary_content)
