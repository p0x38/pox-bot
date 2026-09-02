from datetime import timedelta
from io import BytesIO
from time import perf_counter
from typing import Any

from gtts import gTTS, gTTSError
from gtts.lang import tts_langs

from ....shared.abc.tts_engine import BaseTTSEngine
from ....shared.exceptions.tts_error import SpeechGenerationError
from ..models import TTSMetricsData, TTSRequest, TTSResult


class GoogleTTSEngine(BaseTTSEngine):
    def __init__(self):
        super().__init__()
        self.gtts_languages: dict[str, str] = {}

    async def initialize(self, manager: Any) -> None:
        self.logger.info("Fetching gTTS languages...")
        try:
            self.gtts_languages = tts_langs()
        except Exception:
            self.logger.exception("Failed to fetch gTTS languages during initialization")
        else:
            self.logger.info("Fetched gTTS languages!")
    
    async def generate(self, request: TTSRequest, manager: Any) -> TTSResult:
        start_time = perf_counter()
        abuffer = BytesIO()
        
        lang = request.voice or 'en'
        
        try:
            tts = gTTS(text=request.text, lang=lang)
            tts.write_to_fp(abuffer)
            abuffer.seek(0)
        except gTTSError as e:
            raise SpeechGenerationError(f"gTTS library error: {e}") from e
        
        elapsed = perf_counter() - start_time
        metrics = TTSMetricsData(
            duration=timedelta(seconds=elapsed),
            char_count=len(request.text),
            engine_name="GOOGLE_TTS",
        )
        
        return TTSResult(output=abuffer, media_type="mp3", metrics=metrics)
