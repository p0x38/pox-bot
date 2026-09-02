from poxbot.features.text_transform.models import TransformerRequest
from poxbot.features.text_transform.transformers.image_scramble import (
    ImageGlitchScrambleTransformer,
)


def test_image_glitch_scramble_vectors() -> None:
    """Verify matrix roll behavior matches seeded pseudo-random lines."""
    transformer = ImageGlitchScrambleTransformer()
    payload = 'COMPUTERSCIENCE'
    seed = 1337

    scrambled = transformer.transform(
        TransformerRequest(
            text=payload,
            options={'seed_key': seed},
        ),
    )

    assert scrambled.output != payload

    decoded = transformer.transform(
        TransformerRequest(
            text=scrambled.output,
            decode=True,
            options={'seed_key': seed},
        ),
    )

    assert decoded.output == payload


def test_image_glitch_short_inputs() -> None:
    """Ensure short inputs pass untouched without throwing indexing errors."""
    transformer = ImageGlitchScrambleTransformer()

    result = transformer.transform(
        TransformerRequest(
            text='abc',
            options={'seed_key': 42},
        ),
    )

    assert result.output == 'abc'
