from datetime import timedelta
from io import BytesIO
from time import perf_counter
from typing import Any

from edge_tts import Communicate, list_voices

from ....shared.abc.tts_engine import BaseTTSEngine
from ..models import TTSMetricsData, TTSRequest, TTSResult


class EdgeTTSEngine(BaseTTSEngine):
    def __init__(self):
        super().__init__()
        
        self.edge_tts_voices: list[Any] = []

    async def initialize(self, manager: Any) -> None:
        self.logger.info("Fetching Edge TTS models...")
        try:
            self.edge_tts_voices = await list_voices()
        except Exception:
            self.logger.exception("Failed to fetch Edge TTS voices during initialization")
        else:
            self.logger.info("Fetched Edge TTS models!")
    
    async def generate(self, request: TTSRequest, manager: Any) -> TTSResult:
        start_time = perf_counter()
        abuffer = BytesIO()
        
        speech_voice = request.voice or 'en-US-AndrewMultilingualNeutral'
        
        communicate = Communicate(request.text, speech_voice)
        chunks = 0
        
        async for chunk in communicate.stream():
            chunks += 1
            if chunk['type'] == 'audio' and 'data' in chunk:
                abuffer.write(chunk['data'])
        
        abuffer.seek(0)
        
        elapsed = perf_counter() - start_time
        metrics = TTSMetricsData(
            duration=timedelta(seconds=elapsed),
            char_count=len(request.text),
            engine_name="EDGE_TTS",
            chunk_count=chunks,
        )
        
        return TTSResult(output=abuffer, media_type="mp3", metrics=metrics)
