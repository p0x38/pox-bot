from __future__ import annotations

import contextlib
import io
import os
import shutil
import subprocess  # ruff: ignore[suspicious-subprocess-import]
import tempfile
from pathlib import Path
from typing import Any, BinaryIO

import mido
from pydub import AudioSegment
from pydub.exceptions import CouldntEncodeError

type MIDIInput = (
    str
    | os.PathLike[str]
    | bytes
    | bytearray
    | memoryview
    | BinaryIO
)

type MP3Output = (
    str
    | os.PathLike[str]
    | BinaryIO
    | None
)


class MIDIProcessor:
    """Parse, inspect, and convert MIDI files into MP3 audio."""

    DEFAULT_TEMPO = 500_000

    def __init__(
            self,
            soundfont: str | Path,
            *,
            sample_rate: int = 44100,
            gain: float = 0.2,
            bitrate: str = "192k",
            fluidsynth_executable: str = "",
    ) -> None:
        self.soundfont = Path(soundfont).expanduser().resolve()
        self.sample_rate = sample_rate
        self.gain = gain
        self.bitrate = bitrate
        self.fluidsynth_executable = fluidsynth_executable

        if not fluidsynth_executable.strip():
            executable = shutil.which("fluidsynth")

            if executable is None:
                raise FileNotFoundError("FluidSynth was not found.")

            self.fluidsynth_executable = executable

        if sample_rate <= 0:
            raise ValueError("sample_rate must be positive.")

        if gain < 0:
            raise ValueError("gain cannot be negative.")

        if not bitrate:
            raise ValueError("bitrate cannot be empty.")

    @staticmethod
    def _read_midi_bytes(source: MIDIInput) -> bytes:
        """Read MIDI data from a path, bytes, or binary stream."""

        if isinstance(source, (str, os.PathLike)):
            return Path(source).expanduser().read_bytes()

        if isinstance(source, (bytes, bytearray, memoryview)):
            return bytes(source)

        getvalue = getattr(source, "getvalue", None)

        if callable(getvalue):
            data = getvalue()
        else:
            original_position: int | None = None

            try:
                original_position = source.tell()
                source.seek(0)
            except (AttributeError, OSError, ValueError):
                original_position = None

            try:
                data = source.read()
            finally:
                if original_position is not None:
                    with contextlib.suppress(AttributeError, OSError, ValueError):
                        source.seek(original_position)

        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError("MIDI input must contain binary data.")

        return bytes(data)

    @classmethod
    def _load_midi(cls, source: MIDIInput) -> mido.MidiFile:
        """Parse MIDI data without changing the input stream's position."""

        data = cls._read_midi_bytes(source)

        try:
            midi = mido.MidiFile(file=io.BytesIO(data))
        except Exception as exc:
            raise ValueError("Could not parse the MIDI input") from exc

        if not midi.tracks:
            raise ValueError("The MIDI file contains no tracks.")

        return midi

    @staticmethod
    def _get_track_name(track: mido.MidiTrack) -> str | None:
        for message in track:
            if message.is_meta and message.type == "track_name":
                return message.name

        return None

    @classmethod
    def _summarize_tracks(
        cls,
        midi: mido.MidiFile,
    ) -> list[dict[str, Any]]:
        tracks: list[dict[str, Any]] = []

        for index, track in enumerate(midi.tracks):
            channels = sorted(
                {
                    message.channel
                    for message in track
                    if not message.is_meta
                    and hasattr(message, "channel")
                }
            )

            programs: list[dict[str, int]] = []
            absolute_tick = 0

            for message in track:
                absolute_tick += message.time

                if message.type == "program_change":
                    programs.append(
                        {
                            "tick": absolute_tick,
                            "channel": message.channel,
                            "program": message.program,
                        }
                    )

            note_on_count = sum(
                message.type == "note_on" and message.velocity > 0
                for message in track
            )

            note_off_count = sum(
                message.type == "note_off"
                or (
                    message.type == "note_on"
                    and message.velocity == 0
                )
                for message in track
            )

            tracks.append(
                {
                    "index": index,
                    "name": cls._get_track_name(track),
                    "message_count": len(track),
                    "note_on_count": note_on_count,
                    "note_off_count": note_off_count,
                    "channels": channels,
                    "program_changes": programs,
                }
            )

        return tracks

    def get_tracks(
            self,
            source: MIDIInput,
    ) -> list[dict[str, Any]]:
        """Return a summary of every MIDI track."""

        midi = self._load_midi(source)
        return self._summarize_tracks(midi)

    def get_track_events(
            self,
            source: MIDIInput,
            track_index: int,
    ) -> list[dict[str, Any]]:
        """Return all events in a track with absolute tick positions."""

        midi = self._load_midi(source)

        if not 0 <= track_index < len(midi.tracks):
            raise IndexError(
                f"Track index {track_index} is out of range "
                f"for {len(midi.tracks)} tracks."
            )

        events: list[dict[str, Any]] = []
        absolute_tick = 0

        for message in midi.tracks[track_index]:
            absolute_tick += message.time

            details = message.dict()
            delta_ticks = details.pop("time", 0)
            message_type = details.pop("type")

            events.append(
                {
                    "track_index": track_index,
                    "tick": absolute_tick,
                    "delta_ticks": delta_ticks,
                    "type": message_type,
                    **details,
                }
            )

        return events

    def get_note_events(
            self,
            source: MIDIInput,
            track_index: int,
    ) -> list[dict[str, Any]]:
        """Return note-on and note-off events from a track."""

        events = self.get_track_events(source, track_index)
        notes: list[dict[str, Any]] = []

        for event in events:
            if event["type"] not in {"note_on", "note_off"}:
                continue

            event = event.copy()  # ruff: ignore[redefined-loop-name]

            if event["type"] == "note_on" and event.get("velocity") == 0:
                event["type"] = "note_off"

            notes.append(event)

        return notes
    
    def get_instruments(
        self,
        source: MIDIInput,
    ) -> list[dict[str, Any]]:
        """Return explicitly defined instrument program changes.

        Program numbers use General MIDI's zero-based numbering.
        """

        midi = self._load_midi(source)
        instruments: list[dict[str, Any]] = []

        for track_index, track in enumerate(midi.tracks):
            track_name = self._get_track_name(track)
            absolute_tick = 0

            for message in track:
                absolute_tick += message.time

                if message.type != "program_change":
                    continue

                instruments.append(
                    {
                        "track_index": track_index,
                        "track_name": track_name,
                        "tick": absolute_tick,
                        "channel": message.channel,
                        "program": message.program,
                    }
                )

        return instruments

    @staticmethod
    def _get_duration(midi: mido.MidiFile) -> float | None:
        """Return duration in seconds, or None for asynchronous type-2 MIDI."""

        if midi.type == 2:
            return None

        return float(midi.length)

    def get_duration(self, source: MIDIInput) -> float | None:
        """Return the MIDI duration in seconds.

        Type-2 MIDI files contain independent sequences, so there is no
        single well-defined duration for the entire file.
        """

        midi = self._load_midi(source)
        return self._get_duration(midi)

    @classmethod
    def _collect_tempo_changes(
        cls,
        midi: mido.MidiFile,
    ) -> list[dict[str, Any]]:
        changes: list[dict[str, Any]] = []

        # Type-2 tracks are independent sequences and have separate clocks.
        if midi.type == 2:
            streams = enumerate(midi.tracks)
        else:
            streams = [(None, mido.merge_tracks(midi.tracks))]

        for track_index, track in streams:
            absolute_tick = 0
            elapsed_seconds = 0.0
            current_tempo = cls.DEFAULT_TEMPO

            for message in track:
                absolute_tick += message.time

                elapsed_seconds += mido.tick2second(
                    message.time,
                    midi.ticks_per_beat,
                    current_tempo,
                )

                if not message.is_meta or message.type != "set_tempo":
                    continue

                change: dict[str, Any] = {
                    "tick": absolute_tick,
                    "time_seconds": elapsed_seconds,
                    "tempo_us_per_beat": message.tempo,
                    "bpm": mido.tempo2bpm(message.tempo),
                }

                if track_index is not None:
                    change["track_index"] = track_index

                changes.append(change)
                current_tempo = message.tempo

        return changes

    def get_tempo_changes(
        self,
        source: MIDIInput,
    ) -> list[dict[str, Any]]:
        """Return explicit tempo-change events."""

        midi = self._load_midi(source)
        return self._collect_tempo_changes(midi)

    # ------------------------------------------------------------------
    # Metadata events
    # ------------------------------------------------------------------

    @staticmethod
    def _collect_meta_events(
        midi: mido.MidiFile,
        event_types: set[str],
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []

        for track_index, track in enumerate(midi.tracks):
            absolute_tick = 0

            for message in track:
                absolute_tick += message.time

                if not message.is_meta or message.type not in event_types:
                    continue

                details = message.dict()
                details.pop("type", None)
                details.pop("time", None)

                events.append(
                    {
                        "track_index": track_index,
                        "tick": absolute_tick,
                        "type": message.type,
                        **details,
                    }
                )

        events.sort(key=lambda event: (event["tick"], event["track_index"]))
        return events

    def get_time_signatures(
        self,
        source: MIDIInput,
    ) -> list[dict[str, Any]]:
        """Return time-signature events."""

        midi = self._load_midi(source)
        return self._collect_meta_events(midi, {"time_signature"})

    def get_key_signatures(
        self,
        source: MIDIInput,
    ) -> list[dict[str, Any]]:
        """Return key-signature events."""

        midi = self._load_midi(source)
        return self._collect_meta_events(midi, {"key_signature"})

    def get_markers(
        self,
        source: MIDIInput,
    ) -> list[dict[str, Any]]:
        """Return markers and cue markers."""

        midi = self._load_midi(source)
        return self._collect_meta_events(midi, {"marker", "cue_marker"})

    def get_lyrics(
        self,
        source: MIDIInput,
    ) -> list[dict[str, Any]]:
        """Return MIDI lyric events."""

        midi = self._load_midi(source)
        return self._collect_meta_events(midi, {"lyrics"})

    def get_text_events(
        self,
        source: MIDIInput,
    ) -> list[dict[str, Any]]:
        """Return descriptive text events stored in the MIDI."""

        midi = self._load_midi(source)

        return self._collect_meta_events(
            midi,
            {
                "text",
                "copyright",
                "track_name",
                "instrument_name",
            },
        )

    def get_metadata(
        self,
        source: MIDIInput,
    ) -> dict[str, Any]:
        """Return a combined overview of the MIDI file."""

        midi = self._load_midi(source)

        return {
            "format_type": midi.type,
            "ticks_per_beat": midi.ticks_per_beat,
            "track_count": len(midi.tracks),
            "duration_seconds": self._get_duration(midi),
            "tracks": self._summarize_tracks(midi),
            "instruments": self._collect_instruments(midi),
            "tempo_changes": self._collect_tempo_changes(midi),
            "time_signatures": self._collect_meta_events(
                midi, {"time_signature"}
            ),
            "key_signatures": self._collect_meta_events(
                midi, {"key_signature"}
            ),
            "markers": self._collect_meta_events(
                midi, {"marker", "cue_marker"}
            ),
            "lyrics": self._collect_meta_events(midi, {"lyrics"}),
            "text_events": self._collect_meta_events(
                midi,
                {
                    "text",
                    "copyright",
                    "track_name",
                    "instrument_name",
                },
            ),
        }

    @staticmethod
    def _collect_instruments(
        midi: mido.MidiFile,
    ) -> list[dict[str, Any]]:
        instruments: list[dict[str, Any]] = []

        for track_index, track in enumerate(midi.tracks):
            track_name = MIDIProcessor._get_track_name(track)
            absolute_tick = 0

            for message in track:
                absolute_tick += message.time

                if message.type == "program_change":
                    instruments.append(
                        {
                            "track_index": track_index,
                            "track_name": track_name,
                            "tick": absolute_tick,
                            "channel": message.channel,
                            "program": message.program,
                        }
                    )

        return instruments

    # ------------------------------------------------------------------
    # MIDI-to-MP3 conversion
    # ------------------------------------------------------------------

    def convert(
        self,
        source: MIDIInput,
        output: MP3Output = None,
    ) -> Path | BinaryIO:
        """Convert MIDI input into an MP3 file or binary stream.

        Args:
            source:
                A MIDI file path, bytes, or binary file-like object.
            output:
                An MP3 output path or writable binary stream.
                If omitted, a new BytesIO containing the MP3 is returned.

        Returns:
            The destination Path or the output binary stream.
            For stream output, the cursor is positioned at the beginning.
        """

        midi_data = self._read_midi_bytes(source)

        # Validate the MIDI before launching the synthesizer.
        self._load_midi(midi_data)

        destination: Path | None = None
        output_stream: BinaryIO | None = None

        if output is None:
            output_stream = io.BytesIO()

        elif isinstance(output, (str, os.PathLike)):
            destination = Path(output).expanduser().resolve()

            if destination.suffix.lower() != ".mp3":
                raise ValueError("The output file must have an .mp3 extension.")

            if isinstance(source, (str, os.PathLike)):
                source_path = Path(source).expanduser().resolve()

                if source_path == destination:
                    raise ValueError(
                        "Input and output paths must be different."
                    )

            destination.parent.mkdir(parents=True, exist_ok=True)

        elif callable(getattr(output, "write", None)):
            output_stream = output

        else:
            raise TypeError(
                "output must be a path, writable binary stream, or None."
            )

        if not self.soundfont.is_file():
            raise FileNotFoundError(
                f"SoundFont file not found: {self.soundfont}"
            )

        executable = shutil.which(self.fluidsynth_executable)

        if executable is None:
            raise FileNotFoundError(
                "FluidSynth was not found. Install it or configure "
                "fluidsynth_executable."
            )

        with tempfile.TemporaryDirectory(
            prefix="midi_processor_"
        ) as temporary_directory:
            temporary_path = Path(temporary_directory)

            midi_path = temporary_path / "input.mid"
            wav_path = temporary_path / "rendered.wav"
            mp3_path = temporary_path / "rendered.mp3"

            midi_path.write_bytes(midi_data)

            command = [
                executable,
                "-ni",
                "-g",
                str(self.gain),
                "-r",
                str(self.sample_rate),
                "-T",
                "wav",
                "-F",
                str(wav_path),
                str(self.soundfont),
                str(midi_path),
            ]

            try:
                subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true]
                    command,
                    shell=False,
                    check=True,
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError(
                    "FluidSynth timed out while rendering the MIDI file.",
                ) from exc
            except subprocess.CalledProcessError as exc:
                details = (exc.stderr or exc.stdout or "").strip()

                raise RuntimeError(
                    "FluidSynth failed to render the MIDI file."
                    + (f"\n{details}" if details else "")
                ) from exc

            if not wav_path.is_file() or wav_path.stat().st_size == 0:
                raise RuntimeError(
                    "FluidSynth did not produce a valid WAV file."
                )

            try:
                audio = AudioSegment.from_wav(str(wav_path))
                encoded_file = audio.export(
                    str(mp3_path),
                    format="mp3",
                    bitrate=self.bitrate,
                )
                encoded_file.close()

            except (FileNotFoundError, CouldntEncodeError) as exc:
                raise RuntimeError(
                    "MP3 encoding failed. Ensure FFmpeg is installed "
                    "and accessible to pydub."
                ) from exc

            if not mp3_path.is_file() or mp3_path.stat().st_size == 0:
                raise RuntimeError("MP3 encoding produced no output.")

            if destination is not None:
                staging_path: Path | None = None

                try:
                    # Stage in the destination directory so replacement
                    # happens on the same filesystem.
                    with tempfile.NamedTemporaryFile(
                        prefix=f".{destination.stem}.",
                        suffix=".mp3",
                        dir=destination.parent,
                        delete=False,
                    ) as staging_file:
                        staging_path = Path(staging_file.name)

                    shutil.copyfile(mp3_path, staging_path)
                    Path(staging_path).replace(destination)
                    staging_path = None

                finally:
                    if staging_path is not None:
                        staging_path.unlink(missing_ok=True)

                return destination

            assert output_stream is not None  # ruff: ignore[assert]

            # Replace existing stream contents and rewind for the caller.
            try:
                output_stream.seek(0)
                output_stream.truncate(0)
            except (AttributeError, OSError, ValueError):
                pass

            output_stream.write(mp3_path.read_bytes())

            with contextlib.suppress(AttributeError, OSError, ValueError):
                output_stream.seek(0)

            return output_stream
