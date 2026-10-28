# tests/tts/pocket/test_pocket_engine.py

import asyncio
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from poxbot.features.tts.engines.pocket import PocketTTSEngine
from poxbot.features.tts.models import TTSRequest
from poxbot.shared.enums.tts import TTSEngineType


@pytest.mark.asyncio
async def test_initialize_defers_model_loading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_load() -> None:
        pytest.fail('Pocket-TTS model loading must be deferred during initialize().')

    monkeypatch.setattr(
        PocketTTSEngine,
        '_load_model',
        staticmethod(unexpected_load),
    )

    custom_voice = SimpleNamespace(
        name='custom',
        friendly_name='Custom',
        model=Path('/assets/custom.safetensors'),
    )
    builtin_voice = SimpleNamespace(
        name='alba',
        friendly_name='Alba',
        model=Path('/assets/alba'),
    )
    manager = SimpleNamespace(
        tts_models={
            TTSEngineType.POCKET_TTS: {
                'custom': [custom_voice],
                'builtin': [builtin_voice],
            },
        },
    )

    engine = PocketTTSEngine()
    await engine.initialize(manager)

    assert engine.pocket_tts_model is None
    assert engine.status == 'unloaded'
    assert engine.custom_models == [custom_voice]
    assert engine.builtin_models == [builtin_voice]


@pytest.mark.asyncio
async def test_model_loading_is_cached_under_concurrency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeModel:
        sample_rate = 22050

    calls = 0

    def load_model() -> FakeModel:
        nonlocal calls
        calls += 1
        return FakeModel()

    monkeypatch.setattr(
        PocketTTSEngine,
        '_load_model',
        staticmethod(load_model),
    )

    engine = PocketTTSEngine()
    first, second = await asyncio.gather(
        engine._ensure_model_loaded(),
        engine._ensure_model_loaded(),
    )

    assert calls == 1
    assert first is second
    assert engine.pocket_tts_model is first
    assert engine.sample_rate == 22050
    assert engine.status == 'loaded'


@pytest.mark.asyncio
async def test_builtin_autocomplete_path_resolves_to_builtin_voice_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    builtin_voice = SimpleNamespace(
        name='alba',
        friendly_name='Alba',
        model=Path('C:/assets/alba'),
    )
    engine = PocketTTSEngine()
    engine.builtin_models = [builtin_voice]

    fake_model = object()
    ensure_model_loaded = AsyncMock(return_value=fake_model)

    captured: dict[str, object] = {}

    def generate_audio(
        model: object,
        sample_rate: int,
        voice: str,
        text: str,
    ) -> BytesIO:
        captured.update(
            model=model,
            sample_rate=sample_rate,
            voice=voice,
            text=text,
        )
        return BytesIO(b'audio')

    monkeypatch.setattr(
        engine,
        '_ensure_model_loaded',
        ensure_model_loaded,
    )
    monkeypatch.setattr(
        engine,
        '_generate_audio',
        generate_audio,
    )

    request = TTSRequest(
        text='hello',
        voice=str(builtin_voice.model),
        engine_type=TTSEngineType.POCKET_TTS.value,
    )
    result = await engine.generate(request, SimpleNamespace())

    assert captured['model'] is fake_model
    assert captured['voice'] == 'alba'
    assert captured['text'] == 'hello'
    assert result.output.getvalue() == b'audio'
    assert result.media_type == 'wav'
