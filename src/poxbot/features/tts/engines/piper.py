import asyncio
import os
import tempfile
import wave
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from time import perf_counter
from typing import Any

from piper import PiperVoice, SynthesisConfig
from piper.download_voices import download_voice

from ....shared.abc.tts_engine import BaseTTSEngine
from ....shared.utils.app_path import app_dir
from ..models import TTSMetricsData, TTSRequest, TTSResult


class PiperTTSEngine(BaseTTSEngine):
    def __init__(self):
        super().__init__()

        self.voice_dir = app_dir.site_data_path / 'voices' / 'piper'

        self._voices: dict[str, PiperVoice] = {}
        self._voice_load_lock = asyncio.Lock()

    async def initialize(self, manager: Any) -> None:
        voice_name = 'en_US-ryan-high'

        model_path = self.voice_dir / f'{voice_name}.onnx'
        config_path = model_path.with_suffix('.onnx.json')

        self.logger.info('Loading Piper TTS model...')

        try:
            self.voice_dir.mkdir(parents=True, exist_ok=True)

            if not model_path.is_file() or not config_path.is_file():
                self.logger.info(
                    'Piper voice "%s" is missing; downloading it...',
                    voice_name,
                )

                await asyncio.to_thread(
                    download_voice,
                    voice_name,
                    self.voice_dir,
                )

            if not model_path.is_file() or not config_path.is_file():
                raise FileNotFoundError(
                    f'Piper voice files are missing after download: {voice_name}'
                )

            manager.piper_voice = await asyncio.to_thread(
                PiperVoice.load,
                str(model_path),
            )
        except Exception:
            self.logger.exception('Failed to load Piper model during initialization')
            raise

        else:
            self.logger.info('Loaded Piper TTS model!')

    @staticmethod
    def _is_valid_file(path: Path) -> bool:
        return path.is_file() and path.stat().st_size > 0

    async def _get_voice(
        self,
        requested_voice: str | None,
        manager: Any,
    ) -> PiperVoice:
        config = manager.bot.settings.piper_tts
        voice_name = requested_voice or config.default_voice

        if voice_name not in config.allowed_voices:
            raise ValueError(
                f'Piper voice {voice_name!r} is not allowed. '
                'Choose an available voice from the command suggestions.',
            )

        async with self._voice_load_lock:
            cached_voice = self._voices.get(voice_name)
            if cached_voice is not None:
                return cached_voice

        self.voice_dir.mkdir(parents=True, exist_ok=True)

        model_path = self.voice_dir / f'{voice_name}.onnx'
        config_path = self.voice_dir / f'{voice_name}.onnx.json'

        if not (self._is_valid_file(model_path) and self._is_valid_file(config_path)):
            self.logger.info(
                'Downloading Piper voice "%s"...',
                voice_name,
            )

            with tempfile.TemporaryDirectory(
                prefix='.piper-download-',
                dir=self.voice_dir,
            ) as temp_dir:
                temp_path = Path(temp_dir)

                await asyncio.to_thread(
                    download_voice,
                    voice_name,
                    temp_path,
                )

                downloaded_model = temp_path / f'{voice_name}.onnx'
                downloaded_config = temp_path / f'{voice_name}.onnx.json'

                for path in (downloaded_model, downloaded_config):
                    if not self._is_valid_file(path):
                        raise RuntimeError(
                            f'Piper download did not produce a valid file: {path.name}',
                        )

                await asyncio.to_thread(
                    os.replace,
                    downloaded_model,
                    model_path,
                )
                await asyncio.to_thread(
                    os.replace,
                    downloaded_config,
                    config_path,
                )

        if not (self._is_valid_file(model_path) and self._is_valid_file(config_path)):
            raise FileNotFoundError(
                f'Piper voice files are missing for {voice_name!r}.',
            )

        self.logger.info(
            'Loading Piper voice "%s"...',
            voice_name,
        )

        voice = await asyncio.to_thread(
            PiperVoice.load,
            str(model_path),
        )

        self._voices[voice_name] = voice

        self.logger.info(
            'Loaded Piper voice "%s".',
            voice_name,
        )

        return voice

    async def generate(self, request: TTSRequest, manager: Any) -> TTSResult:
        start_time = perf_counter()

        piper_voice = await self._get_voice(
            request.voice,
            manager,
        )

        options = request.extra_options
        config = SynthesisConfig(
            speaker_id=options.get('speaker_id'),
            length_scale=options.get('length_scale', 1.0),
            noise_scale=options.get('noise_scale', 0.667),
            noise_w_scale=options.get('noise_w_scale', 0.8),
            normalize_audio=options.get('normalize', True),
            volume=options.get('volume', 1.0),
        )

        abuffer = BytesIO()

        with wave.open(abuffer, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(piper_voice.config.sample_rate)

            generated_chunks = await asyncio.to_thread(
                lambda: list(
                    piper_voice.synthesize(
                        request.text,
                        config,
                    ),
                ),
            )

            for chunk in generated_chunks:
                wav_file.writeframes(chunk.audio_int16_bytes)

        abuffer.seek(0)

        metrics = TTSMetricsData(
            duration=timedelta(seconds=perf_counter() - start_time),
            char_count=len(request.text),
            engine_name='PIPER_TTS',
        )

        return TTSResult(output=abuffer, media_type='wav', metrics=metrics)
