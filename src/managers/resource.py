import os
from pathlib import Path
from typing import Any

import orjson
from aiohttp import ClientSession
from gtts.lang import tts_langs
from profanityfilter import ProfanityFilter
from psutil import Process
from roblox import Client as RbxClient
from urlextract import URLExtract
import aiofiles

from src.models.contributor import ContributorItem

from ..utils import Cache


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

        self.root_path = Path(__file__).resolve().parent.parent.parent
        self.assets_path = self.root_path / "src" / "assets"

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
            raise FileNotFoundError(f"Asset not found at: {target_path}")
        return target_path

    def load_json_asset(self, *paths: str) -> dict[str, Any]:
        file_path = self.get_asset_path(*paths)

        with open(file_path, encoding="utf-8") as f:
            return orjson.loads(f.read())
    
    async def load_json_asset_async(self, *paths: str) -> dict[str, Any] | list[Any]:
        file_path = self.get_asset_path(*paths)

        async with aiofiles.open(file_path, encoding="utf-8") as f:
            content = await f.read()
            return orjson.loads(content)

    def read_text_asset(self, *paths: str) -> str:
        file_path = self.get_asset_path(*paths)
        return file_path.read_text(encoding="utf-8")
    
    async def load_contributors_async(self, *paths: str) -> list[ContributorItem]:
        raw_data = await self.load_json_asset_async(*paths)
        
        if not isinstance(raw_data, list):
            raise ValueError(
                f"Expected a list of contributors, got {type(raw_data)}"
            )
        
        return [ContributorItem.model_validate(item) for item in raw_data]
