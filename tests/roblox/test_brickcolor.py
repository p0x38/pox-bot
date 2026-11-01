import pytest

from poxbot.features.roblox.brickcolor import BrickColor, Color3


def test_color3_from_rgb_accepts_float_channels() -> None:
    color = Color3.from_rgb(255.0, 127.5, 0.0)

    assert color.rgb == (255, 128, 0)


def test_color3_rejects_boolean_channels() -> None:
    with pytest.raises(TypeError):
        Color3(True, 0.0, 0.0)


def test_color3_hex_round_trip() -> None:
    color = Color3.from_hex('#FF8000')

    assert color.to_hex(include_hash=True) == '#FF8000'


def test_brick_color_palette_lookup() -> None:
    assert BrickColor.palette(87).number == 1
    assert BrickColor.palette(87).name == 'White'
