import pytest
from pydantic import ValidationError

from poxbot.config.schema import PiperTTSConfig


@pytest.mark.parametrize(
    'voice',
    [
        'en_US-danny-low',
        'en_US-ryan-high',
        'en_US-hfc_male-medium',
        'ja_JP-hi_fi_captain-medium',
    ],
)
def test_accepts_valid_piper_voice_ids(voice: str) -> None:
    config = PiperTTSConfig(
        default_voice=voice,
        allowed_voices=[voice],
    )

    assert config.allowed_voices == [voice]


@pytest.mark.parametrize(
    'voice',
    [
        'enUS-ryan-high',
        'en_us-ryan-high',
        'en_US--medium',
        'en_US-ryan-',
    ],
)
def test_rejects_valid_piper_voice_ids(voice: str) -> None:
    with pytest.raises(
        ValidationError,
        match='Invalid Piper voice identifiers',
    ):
        PiperTTSConfig(
            default_voice=voice,
            allowed_voices=[voice],
        )
