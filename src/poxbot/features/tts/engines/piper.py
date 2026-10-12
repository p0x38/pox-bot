import asyncio
import importlib.metadata
import os
import re
import tempfile
import wave
from datetime import timedelta
from io import BytesIO
from pathlib import Path
from time import perf_counter
from typing import Any

import aiofiles
import aiohttp
from packaging.specifiers import SpecifierSet
from piper import PiperVoice, SynthesisConfig

from ....shared.abc.tts_engine import BaseTTSEngine
from ....shared.utils.app_path import app_dir
from ..models import TTSMetricsData, TTSProgressCallback, TTSRequest, TTSResult

extras_require = {
    'zh': [
        'g2pW>=0.1.1,<1',
        'transformers>=4,<6',
        'sentence-stream>=1.2.1,<2',
        'unicode-rbnf>=2.4.0,<3',
    ],
    'ja': [
        'pyopenjtalk-plus>=0.4,<1',
    ],
    'th': [
        'tltk>=1.6.8,<1.11',
        'pandas>=2,<3',
        'requests>=2,<3',
        'unicode-rbnf>=2.4.0,<3',
    ],
}


def check_extras_availability(extras_dict):
    results = {}

    for lang, packages in extras_dict.items():
        results[lang] = {'available': True, 'details': []}

        for pkg_requirement in packages:
            match = re.match(r'^([a-zA-Z0-9_\-]+)\s*(.*)$', pkg_requirement)
            if not match:
                continue

            pkg_name, spec_str = match.groups()

            try:
                installed_version = importlib.metadata.version(pkg_name)

                if spec_str:
                    specifier = SpecifierSet(spec_str)
                    is_satisfied = specifier.contains(installed_version)
                else:
                    is_satisfied = True

                if is_satisfied:
                    results[lang]['details'].append(
                        f'{pkg_name} ({installed_version}): OK',
                    )
                else:
                    results[lang]['details'].append(
                        f'{pkg_name} ({installed_version}): Version incompatible '
                        f'(Expected value: {spec_str})',
                    )
                    results[lang]['available'] = False
            except importlib.metadata.PackageNotFoundError:
                results[lang]['details'].append(
                    f'{pkg_name}: Not installed',
                )
                results[lang]['available'] = False

    return results


status = check_extras_availability(extras_require)


class PiperTTSEngine(BaseTTSEngine):
    def __init__(self):
        super().__init__()

        self.voice_dir = app_dir.user_data_path / 'voices' / 'piper'

        self._voices: dict[str, PiperVoice] = {}
        self._voice_load_lock = asyncio.Lock()

    async def initialize(self, manager: Any) -> None:
        self.logger.info(
            'Piper TTS initialized; voices will be loaded on demand.',
        )

    @staticmethod
    def _is_valid_file(path: Path) -> bool:
        return path.is_file() and path.stat().st_size > 0

    @staticmethod
    def _voice_urls(voice_name: str) -> tuple[str, str]:
        try:
            language_code, speaker_name, quality = voice_name.split('-', maxsplit=2)
            language_family = language_code.split('_', maxsplit=1)[0]
        except ValueError as exc:
            raise ValueError(
                f'Invalid Piper voice identifier: {voice_name!r}',
            ) from exc

        base_url = (
            'https://huggingface.co/rhasspy/piper-voices/resolve/main/'
            f'{language_family}/{language_code}/{speaker_name}/{quality}/{voice_name}'
        )

        return (
            f'{base_url}.onnx?download=true',
            f'{base_url}.onnx.json?download=true',
        )

    async def _download_file(
        self,
        session: aiohttp.ClientSession,
        url: str,
        destination: Path,
        progress_callback: TTSProgressCallback | None = None,
    ) -> None:
        async with session.get(url) as response:
            response.raise_for_status()

            total_bytes = int(response.headers.get('Content-Length') or 0)
            downloaded_bytes = 0

            if progress_callback is not None and destination.name.endswith('.onnx'):
                await progress_callback(
                    destination.name,
                    0,
                    total_bytes,
                )

            async with aiofiles.open(destination, 'wb') as file:
                async for chunk in response.content.iter_chunked(1024 * 1024):
                    await file.write(chunk)
                    downloaded_bytes += len(chunk)

                    if progress_callback is not None and destination.name.endswith(
                        '.onnx'
                    ):
                        await progress_callback(
                            destination.name,
                            downloaded_bytes,
                            total_bytes,
                        )

            if downloaded_bytes == 0:
                raise RuntimeError(
                    f'Piper download returned an empty file: {destination.name}',
                )

            if total_bytes and downloaded_bytes != total_bytes:
                raise RuntimeError(
                    f'Incomplete Piper download for {destination.name}: '
                    f'{downloaded_bytes} of {total_bytes} bytes.',
                )

    async def _get_voice(
        self,
        requested_voice: str | None,
        manager: Any,
        progress_callback: TTSProgressCallback | None = None,
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

            if not (
                self._is_valid_file(model_path) and self._is_valid_file(config_path)
            ):
                model_url, config_url = self._voice_urls(voice_name)

                self.logger.info(
                    'Downloading Piper voice "%s"...',
                    voice_name,
                )

                timeout = aiohttp.ClientTimeout(
                    total=None,
                    connect=15,
                    sock_connect=15,
                    sock_read=60,
                )

                with tempfile.TemporaryDirectory(
                    prefix='.piper-download-',
                    dir=self.voice_dir,
                ) as temp_dir:
                    temp_path = Path(temp_dir)

                    downloaded_model = temp_path / model_path.name
                    downloaded_config = temp_path / config_path.name

                    async with aiohttp.ClientSession(
                        timeout=timeout,
                        trust_env=True,
                    ) as session:
                        await self._download_file(
                            session,
                            model_url,
                            downloaded_model,
                            progress_callback,
                        )
                        await self._download_file(
                            session,
                            config_url,
                            downloaded_config,
                        )

                    for path in (downloaded_model, downloaded_config):
                        if not self._is_valid_file(path):
                            raise RuntimeError(
                                'Piper download did not produce a valid file: '
                                f'{path.name}',
                            )

                    await asyncio.to_thread(
                        os.replace,
                        downloaded_config,
                        config_path,
                    )
                    await asyncio.to_thread(
                        os.replace,
                        downloaded_model,
                        model_path,
                    )

            if not (
                self._is_valid_file(model_path) and self._is_valid_file(config_path)
            ):
                raise FileNotFoundError(
                    f'Piper voice files are missing for {voice_name!r}.',
                )

            self.logger.info(
                'Loading Piper voice "%s"...',
                voice_name,
            )

            try:
                voice = await asyncio.to_thread(
                    PiperVoice.load,
                    str(model_path),
                )
            except Exception:
                for path in (model_path, config_path):
                    try:
                        path.unlink(missing_ok=True)
                    except OSError:
                        self.logger.exception(
                            'Failed to remove invalid Piper cache file: %s',
                            path,
                        )

                self.logger.exception(
                    'Piper voice "%s" failed to load; removed cached files.',
                    voice_name,
                )
                raise

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
            request._progress_callback,
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
