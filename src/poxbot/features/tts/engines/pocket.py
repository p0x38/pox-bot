from datetime import timedelta
from io import BytesIO
from time import perf_counter
from typing import Any

from pocket_tts import TTSModel
from scipy.io.wavfile import write

from ....shared.abc.tts_engine import BaseTTSEngine
from ....shared.exceptions.tts_error import (
    NoAvailableModelError,
    VoiceModelNotLoadedError,
)
from ..models import TTSMetricsData, TTSRequest, TTSResult


class PocketTTSEngine(BaseTTSEngine):
    def __init__(self):
        super().__init__()

        self.pocket_tts_model: TTSModel | None = None
        self.sample_rate: int = 24000
        self.status: str = 'unloaded'

        self.custom_models: list[Any] = []
        self.builtin_models: list[Any] = []

    async def initialize(self, manager: Any) -> None:
        self.logger.info('Loading Pocket-TTS models...')
        try:
            self.pocket_tts_model = TTSModel.load_model()
            self.sample_rate = getattr(self.pocket_tts_model, 'sample_rate', 24000)
            self.status = 'loaded'

            self.logger.info('Pocket-TTS model loaded successfully!')

            raw_pocket_data = manager.tts_models.get('POCKET_TTS', {})
            self.custom_models = raw_pocket_data.get('custom', [])
            self.builtin_models = raw_pocket_data.get('builtin', [])
            self.logger.info('Synchronized Pocket-TTS model info into manager!')
        except Exception:
            self.status = 'error'
            self.logger.exception(
                'Failed to initialize Pocket-TTSduring initialization',
            )
            raise
        else:
            self.logger.info('Loaded Pocket TTS models!')

    async def generate(self, request: TTSRequest, manager: Any) -> TTSResult:
        start_time = perf_counter()

        if not self.pocket_tts_model:
            from ....shared.enums.tts import (  # ruff: ignore[import-outside-top-level]
                TTSEngineType,
            )

            raise VoiceModelNotLoadedError(TTSEngineType.POCKET_TTS)

        _opts = request.extra_options
        speech_voice = request.voice
        all_models = self.custom_models + self.builtin_models

        if speech_voice:
            for voice_data in all_models:
                if (
                    speech_voice.lower() in voice_data.name.lower()
                    or speech_voice.lower() in voice_data.friendly_name.lower()
                ):
                    speech_voice = str(voice_data.model)
                    break
            else:
                speech_voice = None

        if not speech_voice and self.custom_models:
            speech_voice = str(self.custom_models[0].model)

        if speech_voice is None:
            from ....shared.enums.tts import (  # ruff: ignore[import-outside-top-level]
                TTSEngineType,
            )

            raise NoAvailableModelError(TTSEngineType.POCKET_TTS)

        if speech_voice.startswith('assets:'):
            relative_path = speech_voice.split(':', 1)[1].lstrip('/')
            resolved_path = manager.bot.resources.get_asset_path(relative_path)
            speech_voice = str(resolved_path)

        abuffer = BytesIO()

        voice_state = self.pocket_tts_model.get_state_for_audio_prompt(
            audio_conditioning=speech_voice,
        )
        generated = self.pocket_tts_model.generate_audio(voice_state, request.text)

        write(abuffer, self.pocket_tts_model.sample_rate, generated.numpy())
        abuffer.seek(0)

        elapsed = perf_counter() - start_time
        metrics = TTSMetricsData(
            duration=timedelta(seconds=elapsed),
            char_count=len(request.text),
            engine_name='POCKET_TTS',
        )

        return TTSResult(output=abuffer, media_type='wav', metrics=metrics)
