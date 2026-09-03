from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..enums.tts import TTSEngineType


class TTSError(Exception):
    pass


class InvalidInputError(TTSError):
    pass


class EmptyInputError(InvalidInputError):
    def __init__(self, *args):
        super().__init__('Input text cannot be empty', *args)


class TooLongTextError(InvalidInputError):
    def __init__(self, *args):
        super().__init__('Input is too long to process', *args)


class ModelError(TTSError):
    pass


class VoiceModelNotLoadedError(ModelError):
    def __init__(self, model: TTSEngineType, *args):
        super().__init__(f'Voice model for {model} is not yet available', *args)


class NoAvailableModelError(ModelError):
    def __init__(self, model: TTSEngineType, *args):
        super().__init__(f'No available models for {model} can be found', *args)


class UnknownEngineError(TTSError):
    def __init__(self, *args):
        super().__init__('You tried to load engine that is not exists', *args)


class UnimplementedEngineError(TTSError):
    def __init__(self, *args):
        super().__init__('You tried to load engine that is not implemented yet', *args)


class SpeechGenerationError(TTSError):
    pass


class SpeechValidationError(TTSError):
    pass


class EmptyResponseError(SpeechValidationError):
    def __init__(self, *args):
        super().__init__('Result returned None', *args)
