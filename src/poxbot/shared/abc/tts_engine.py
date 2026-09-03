from abc import ABC, abstractmethod
from typing import Any

from ...features.tts.models import TTSRequest, TTSResult
from ...infrastructure.logger import get_logger


class BaseTTSEngine(ABC):
    def __init__(self):
        self.logger = get_logger(__name__, prefix='TTSEngine')

    @abstractmethod
    async def initialize(self, manager: Any) -> None:
        pass

    @abstractmethod
    async def generate(self, request: TTSRequest, manager: Any) -> TTSResult:
        pass
