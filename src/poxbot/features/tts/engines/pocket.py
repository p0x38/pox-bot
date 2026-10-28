import asyncio
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING, Any

from ....shared.abc.tts_engine import BaseTTSEngine
from ....shared.enums.tts import TTSEngineType
from ....shared.exceptions.tts_error import (
    NoAvailableModelError,
    VoiceModelNotLoadedError,
)
from ..models import TTSMetricsData, TTSRequest, TTSResult

if TYPE_CHECKING:
    from pocket_tts import TTSModel


class PocketTTSEngine(BaseTTSEngine):
    def __init__(self):
        super().__init__()

        self.pocket_tts_model: TTSModel | None = None
        self.sample_rate: int = 24000
        self.status: str = 'unloaded'

        self.custom_models: list[Any] = []
        self.builtin_models: list[Any] = []

        self._model_lock = asyncio.Lock()
        self._generation_lock = asyncio.Lock()

    @staticmethod
    def _load_model() -> TTSModel:
        from pocket_tts import TTSModel  # ruff: ignore[import-outside-top-level]

        return TTSModel.load_model()

    @staticmethod
    def _generate_audio(
        model: TTSModel,
        sample_rate: int,
        voice: str,
        text: str,
    ) -> BytesIO:
        from scipy.io.wavfile import write  # ruff: ignore[import-outside-top-level]

        voice_state = model.get_state_for_audio_prompt(
            audio_conditioning=voice,
        )
        generated = model.generate_audio(voice_state, text)

        output = BytesIO()
        write(output, sample_rate, generated.numpy())
        output.seek(0)

        return output

    async def initialize(self, manager: Any) -> None:
        pocket_data = manager.tts_models.get(TTSEngineType.POCKET_TTS, {})
        self.custom_models = pocket_data.get('custom', [])
        self.builtin_models = pocket_data.get('builtin', [])

        self.logger.info(
            'Pocket-TTS initialized; model loading is deferred until first one.',
        )

    async def _ensure_model_loaded(self) -> TTSModel:
        if self.pocket_tts_model is not None:
            return self.pocket_tts_model

        async with self._model_lock:
            if self.pocket_tts_model is not None:
                return self.pocket_tts_model

            self.status = 'loading'

            try:
                model = await asyncio.to_thread(self._load_model)
            except Exception as exc:
                self.status = 'error'
                self.logger.exception(
                    'Failed to load Pocket-TTS model on demand.',
                )
                raise VoiceModelNotLoadedError(
                    TTSEngineType.POCKET_TTS,
                ) from exc

            self.pocket_tts_model = model
            self.sample_rate = getattr(model, 'sample_rate', 24000)
            self.status = 'loaded'

            self.logger.info('Pocket-TTS model loaded on demand.')
            return model

    async def generate(
        self,
        request: TTSRequest,
        manager: Any,
    ) -> TTSResult:
        start_time = perf_counter()
        speech_voice = request.voice
        all_models = self.custom_models + self.builtin_models

        if speech_voice:
            requested_voice = speech_voice.casefold()

            for voice_data in all_models:
                model_path = Path(voice_data.model)
                candidates = (
                    voice_data.name,
                    voice_data.friendly_name,
                    str(model_path),
                )

                if any(
                    requested_voice in candidate.casefold() for candidate in candidates
                ):
                    speech_voice = (
                        str(model_path) if model_path.suffix else voice_data.name
                    )
                    break
            else:
                speech_voice = None

        if not speech_voice:
            if self.custom_models:
                speech_voice = str(self.custom_models[0].model)
            elif self.builtin_models:
                speech_voice = self.builtin_models[0].name

        if speech_voice is None:
            raise NoAvailableModelError(TTSEngineType.POCKET_TTS)

        if speech_voice.startswith('assets:'):
            relative_path = speech_voice.split(':', 1)[1].lstrip('/')
            resolved_path = manager.bot.resources.get_asset_path(relative_path)
            speech_voice = str(resolved_path)

        async with self._generation_lock:
            model = await self._ensure_model_loaded()
            output = await asyncio.to_thread(
                self._generate_audio,
                model,
                self.sample_rate,
                speech_voice,
                request.text,
            )

        metrics = TTSMetricsData(
            duration=timedelta(seconds=perf_counter() - start_time),
            char_count=len(request.text),
            engine_name='POCKET_TTS',
        )

        return TTSResult(
            output=output,
            media_type='wav',
            metrics=metrics,
        )
