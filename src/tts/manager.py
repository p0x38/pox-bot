import wave
from datetime import datetime
from enum import StrEnum
from io import BytesIO
from typing import Any

from edge_tts import Communicate, list_voices
from gtts import gTTS, gTTSError
from piper import PiperVoice, SynthesisConfig
from pocket_tts import TTSModel
from pytz import UTC
from scipy.io.wavfile import write


class TTSEngineType(StrEnum):
    GOOGLE_TTS = "google-tts"
    PIPER_TTS = "piper-tts"
    ESPEAK_TTS = "espeak-tts"
    POCKET_TTS = "pocket-tts"
    EDGE_TTS = "edge-tts"
    PYTTSX3_TTS = "pyttsx3-tts"


class SpeechGenerationError(Exception):
    pass


class TTSManager:
    def __init__(self, bot):
        self.bot = bot
        self.pocket_tts_model = None
        self.pocket_tts_custom_models = [
            {
                "name": "sam",
                "friendly_name": "Microsoft Sam",
                "path": "/src/assets/voices/pocket-tts/sam.safetensors",
            },
            {
                "name": "zira",
                "friendly_name": "Microsoft Zira",
                "path": "/src/assets/voices/pocket-tts/zira.safetensors",
            },
            {
                "name": "sam-v2",
                "friendly_name": "Microsoft Sam V2",
                "path": "/src/assets/voices/pocket-tts/sam-v2.safetensors",
            },
            {
                "name": "zira-v2",
                "friendly_name": "Microsoft Zira V2",
                "path": "/src/assets/voices/pocket-tts/zira-v2.safetensors",
            },
            {
                "name": "carl",
                "friendly_name": "High pitched TruVoice Adult Male 1",
                "path": "/src/assets/voices/pocket-tts/carl.safetensors",
            },
            {
                "name": "mary",
                "friendly_name": "Microsoft Mary",
                "path": "/src/assets/voices/pocket-tts/mary.safetensors",
            },
            {
                "name": "mike",
                "friendly_name": "Microsoft Mike",
                "path": "/src/assets/voices/pocket-tts/mike.safetensors",
            },
            {
                "name": "truvoice-af1",
                "friendly_name": "TruVoice Adult Female 1",
                "path": "/src/assets/voices/pocket-tts/truvoice-af1.safetensors",
            },
            {
                "name": "truvoice-am1",
                "friendly_name": "TruVoice Adult Male 1",
                "path": "/src/assets/voices/pocket-tts/truvoice-am1.safetensors",
            },
            {
                "name": "missile",
                "friendly_name": "Missile knows where it is",
                "path": "/src/assets/voices/pocket-tts/missile.safetensors",
            },
            {
                "name": "sweep",
                "friendly_name": "Sine Sweep",
                "path": "/src/assets/voices/pocket-tts/sweep.safetensors",
            },
            {
                "name": "triangle-sweep",
                "friendly_name": "Triangle Sweep",
                "path": "/src/assets/voices/pocket-tts/triangle-sweep.safetensors",
            },
            {
                "name": "me",
                "friendly_name": "Me",
                "path": "/src/assets/voices/pocket-tts/me.safetensors",
            },
            {
                "name": "triangle",
                "friendly_name": "Triangle Wave",
                "path": "/src/assets/voices/pocket-tts/triangle.safetensors",
            },
            {
                "name": "sine",
                "friendly_name": "Sine Wave",
                "path": "/src/assets/voices/pocket-tts/sine.safetensors",
            },
            {
                "name": "dtmf",
                "friendly_name": "DTMF Tone",
                "path": "/src/assets/voices/pocket-tts/dtmf.safetensors",
            },
            {
                "name": "vc1",
                "friendly_name": "Voice 1",
                "path": "/src/assets/voices/pocket-tts/vc1.safetensors",
            },
            {
                "name": "vc2",
                "friendly_name": "Voice 2",
                "path": "/src/assets/voices/pocket-tts/vc2.safetensors",
            },
            {
                "name": "vc3",
                "friendly_name": "Voice 3",
                "path": "/src/assets/voices/pocket-tts/vc3.safetensors",
            },
            {
                "name": "vc4",
                "friendly_name": "Voice 4",
                "path": "/src/assets/voices/pocket-tts/vc4.safetensors",
            },
            {
                "name": "vc5",
                "friendly_name": "Voice 5",
                "path": "/src/assets/voices/pocket-tts/vc5.safetensors",
            },
            {
                "name": "vc5-lq",
                "friendly_name": "Voice 5 Low Quality",
                "path": "/src/assets/voices/pocket-tts/vc5-lq.safetensors",
            },
            {
                "name": "vc6",
                "friendly_name": "Voice 6",
                "path": "/src/assets/voices/pocket-tts/vc6.safetensors",
            },
            {
                "name": "gtts",
                "friendly_name": "gTTS",
                "path": "/src/assets/voices/pocket-tts/gtts.safetensors",
            },
        ]
        self.pocket_tts_predefined_models = [
            "alba",
            "giovanni",
            "lola",
            "juergen",
            "rafael",
            "estelle",
            "anna",
            "azelma",
            "bill_boerst",
            "caro_davy",
            "charles",
            "cosette",
            "eponine",
            "eve",
            "fantine",
            "george",
            "jane",
            "jean",
            "javert",
            "marius",
            "mary",
            "michael",
            "paul",
            "peter_yearsley",
            "stuart_bell",
            "vera",
        ]
        self.edge_tts_voices = {}
        self.piper_voice: PiperVoice | None = None

    async def cog_load(self):
        self.pocket_tts_model = TTSModel.load_model()
        self.edge_tts_voices = await list_voices()
        self.piper_voice = PiperVoice.load("./src/assets/voices/en_US-ryan-high.onnx")

    async def generate_speech(self, data: dict[str, Any]):
        if not data.get("input"):
            raise ValueError("Input text is None")

        if isinstance(data["input"], str):
            if not data["input"].strip():
                raise ValueError("Input text cannot be empty")
            if len(data["input"]) > 1500:
                raise RuntimeError("Input too long")

        input_text = data["input"]
        abuffer = BytesIO()
        start_time = datetime.now(UTC)

        match (data["engine"]):
            case TTSEngineType.GOOGLE_TTS:
                try:
                    voice_language = data.get("voice") or "en"
                    slow_mode = data.get("slow_mode") or False

                    generated = gTTS(input_text, lang=voice_language, slow=slow_mode)
                    generated.write_to_fp(abuffer)

                    duration = datetime.now(UTC) - start_time

                    abuffer.seek(0)

                    return {"output": abuffer, "duration": duration, "type": "mp3"}
                except gTTSError as e:
                    raise SpeechGenerationError() from e
            case TTSEngineType.PIPER_TTS:
                if not self.piper_voice:
                    raise RuntimeError("Voice model isn't loaded yet")

                speech_volume = data.get("volume") or 1.0
                length_factor = data.get("length_scale") or 1.0
                noise_factor = data.get("noise_scale") or 0.667
                noise_w_factor = data.get("noise_w_scale") or 0.8
                normalize_audio = data.get("normalize") or True

                synthesis_config = SynthesisConfig(
                    length_scale=length_factor,
                    noise_scale=noise_factor,
                    noise_w_scale=noise_w_factor,
                    normalize_audio=normalize_audio,
                    volume=speech_volume
                )

                with wave.open(abuffer, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(self.piper_voice.config.sample_rate)

                    for raw in await self.bot.loop.run_in_executor(
                        None, lambda: list(self.piper_voice.synthesize(
                            input_text, synthesis_config)) if self.piper_voice else []
                    ):
                        wf.writeframes(raw.audio_int16_bytes)

                duration = datetime.now(UTC) - start_time

                abuffer.seek(0)

                return {"output": abuffer, "duration": duration, "type": "wav"}
            case TTSEngineType.POCKET_TTS:
                speech_voice = data.get("voice")

                if not speech_voice:
                    speech_voice = self.bot.root_path + self.pocket_tts_custom_models[0]['path']

                for voice_data in self.pocket_tts_custom_models:
                    if (speech_voice.lower() in voice_data['name'].lower() or
                        speech_voice.lower() in voice_data['friendly_name'].lower()):
                        speech_voice = self.bot.root_path + voice_data['path']
                        break

                if not self.pocket_tts_model:
                    raise RuntimeError("Voice model isn't loaded yet")

                voice_state = self.pocket_tts_model.get_state_for_audio_prompt(
                    audio_conditioning=speech_voice
                )

                generated = self.pocket_tts_model.generate_audio(voice_state, input_text)

                write(abuffer, self.pocket_tts_model.sample_rate, generated.numpy())

                duration = datetime.now(UTC) - start_time

                abuffer.seek(0)

                return {"output": abuffer, "duration": duration, "type": "wav"}
            case TTSEngineType.EDGE_TTS:
                speech_voice = data.get("voice")

                if not speech_voice:
                    speech_voice = "en-US-AndrewMultilingualNeural"

                communicate = Communicate(input_text, speech_voice)
                chunks = 0

                async for chunk in communicate.stream():
                    chunks += 1
                    if chunk["type"] == "audio" and "data" in chunk:
                        abuffer.write(chunk["data"])

                duration = datetime.now(UTC) - start_time

                abuffer.seek(0)

                return {"output": abuffer, "duration": duration, "chunk_count": chunks, "type": "mp3"}
            case _:
                raise RuntimeError("Unknown engine type")
