import wave
from datetime import timedelta
from io import BytesIO
from time import perf_counter
from typing import Any

from piper import PiperVoice, SynthesisConfig

from ....shared.abc.tts_engine import BaseTTSEngine
from ....shared.exceptions.tts_error import VoiceModelNotLoadedError
from ..models import TTSMetricsData, TTSRequest, TTSResult


class PiperTTSEngine(BaseTTSEngine):
    async def initialize(self, manager: Any) -> None:
        self.logger.info('Loading Piper TTS model...')
        try:
            manager.piper_voice = PiperVoice.load(
                './src/poxbot/assets/voices/en_US-ryan-high.onnx',
            )
        except Exception:
            self.logger.exception('Failed to load Piper model during initialization')
        else:
            self.logger.info('Loaded Piper TTS model!')

    async def generate(self, request: TTSRequest, manager: Any) -> TTSResult:
        start_time = perf_counter()

        piper_voice: PiperVoice | None = getattr(manager, 'piper_voice', None)
        if not piper_voice:
            from ....shared.enums.tts import (  # ruff: ignore[import-outside-top-level]
                TTSEngineType,
            )

            raise VoiceModelNotLoadedError(TTSEngineType.PIPER_TTS)

        opts = request.extra_options
        config = SynthesisConfig(
            speaker_id=opts.get('speaker_id'),
            length_scale=opts.get('length_scale', 1.0),
            noise_scale=opts.get('noise_scale', 0.667),
            noise_w_scale=opts.get('noise_w_scale', 0.8),
            normalize_audio=opts.get('normalize', True),
            volume=opts.get('volume', 1.0),
        )

        abuffer = BytesIO()

        with wave.open(abuffer, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(piper_voice.config.sample_rate)

            loop = manager.bot.loop

            generated_chunks = await loop.run_in_executor(
                None,
                lambda: list(piper_voice.synthesize(request.text, config)),
            )

            for raw in generated_chunks:
                wav_file.writeframes(raw.audio_int16_bytes)

        abuffer.seek(0)

        elapsed = perf_counter() - start_time
        metrics = TTSMetricsData(
            duration=timedelta(seconds=elapsed),
            char_count=len(request.text),
            engine_name='PIPER_TTS',
        )

        return TTSResult(output=abuffer, media_type='wav', metrics=metrics)
