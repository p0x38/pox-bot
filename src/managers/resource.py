import os

from aiohttp import ClientSession
from gtts.lang import tts_langs
from psutil import Process
from roblox import Client as RbxClient
from urlextract import URLExtract

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

    async def initialize(self):
        self.session = ClientSession()

    async def close(self):
        if self.session:
            await self.session.close()
