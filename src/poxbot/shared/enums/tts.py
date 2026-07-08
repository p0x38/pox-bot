from enum import StrEnum


class TTSEngineType(StrEnum):
    GOOGLE_TTS = 'google-tts'
    PIPER_TTS = 'piper-tts'
    ESPEAK_TTS = 'espeak-tts'
    POCKET_TTS = 'pocket-tts'
    EDGE_TTS = 'edge-tts'
    PYTTSX3_TTS = 'pyttsx3-tts'
