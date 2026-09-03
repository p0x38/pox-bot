from __future__ import annotations

from typing import TYPE_CHECKING, Any

import orjson

from ...infrastructure.logger import get_logger
from ...persistence.models.pydantic.tts_model import TTSConfig
from ...shared.enums.tts import TTSEngineType
from ...shared.exceptions.tts_error import (
    EmptyInputError,
    TooLongTextError,
    UnknownEngineError,
)
from .engines.edge import EdgeTTSEngine
from .engines.google import GoogleTTSEngine
from .engines.piper import PiperTTSEngine
from .engines.pocket import PocketTTSEngine
from .models import TTSRequest, TTSResult

if TYPE_CHECKING:
    from ...application import PoxBot
    from ...shared.abc.tts_engine import BaseTTSEngine


class TTSManager:
    def __init__(self, bot: PoxBot):
        self.logger = get_logger(__name__, prefix='TTSManager')
        self.bot = bot

        self.tts_config: TTSConfig | None = None
        self.tts_models: dict = {}

        self.edge_tts_voices: list[dict[str, Any]] = []
        self.gtts_languages: dict[str, str] = {}

        self.engines: dict[TTSEngineType, BaseTTSEngine] = {
            TTSEngineType.GOOGLE_TTS: GoogleTTSEngine(),
            TTSEngineType.PIPER_TTS: PiperTTSEngine(),
            TTSEngineType.EDGE_TTS: EdgeTTSEngine(),
            TTSEngineType.POCKET_TTS: PocketTTSEngine(),
        }

    async def load_tts_models(self) -> None:
        raw_data = await self.bot.resources.load_with_orjson_async(
            'json',
            'voices.json',
        )
        self.tts_config = TTSConfig.model_validate(raw_data)
        self.tts_models = self.tts_config.root

        config_json = self.tts_config.model_dump_json()
        debug_engines = {type_.name: str(eng) for type_, eng in self.engines.items()}
        models_json = orjson.dumps(debug_engines).decode('utf-8')

        self.logger.debug(
            'tts_config: %s\n\ntts_models: %s',
            config_json,
            models_json,
        )

    async def cog_load(self) -> None:
        await self.load_tts_models()

        self.logger.info('Initializing all TTS engines via cog_load...')

        for engine_type, engine in self.engines.items():
            try:
                await engine.initialize(self)
                self.logger.info(
                    'Successfully initialized TTS engine: %s',
                    engine_type.name,
                )
            except Exception:
                self.logger.exception(
                    'Failed to initialize TTS engine %s',
                    engine_type.name,
                )

    async def generate_speech(self, data: dict[str, Any]) -> TTSResult:
        if not data.get('input'):
            raise EmptyInputError()

        input_text = data['input']
        if isinstance(input_text, str):
            if not input_text.strip():
                raise EmptyInputError()
            if len(input_text) > 1500:
                raise TooLongTextError()

        engine_type = data.get('engine')

        if (
            not isinstance(engine_type, TTSEngineType)
            or engine_type not in self.engines
        ):
            raise UnknownEngineError()

        request = TTSRequest(
            text=input_text,
            voice=data.get('voice'),
            engine_type=engine_type.value,
            extra_options=data,
        )

        engine = self.engines[engine_type]
        return await engine.generate(request, self)
