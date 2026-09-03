from poxbot.features.text_transform.models import TransformerRequest
from poxbot.features.text_transform.transformers.caesar import (
    CaesarCipherTransformer,
)
from poxbot.features.text_transform.transformers.morse import (
    MorseCodeTransformer,
)
from poxbot.features.text_transform.transformers.psc1 import Psc1Transformer
from poxbot.features.text_transform.transformers.rail_fence import (
    RailFenceTransformer,
)
from poxbot.features.text_transform.transformers.reverse import (
    ReverseLetterTransformer,
)


def test_reverse_letter_cipher() -> None:
    """Verify alphanumeric mirroring via lookup tables."""
    transformer = ReverseLetterTransformer()

    encoded = transformer.transform(
        TransformerRequest(
            text='abc12',
            options={'type': 'letters'},
        ),
    )

    assert encoded.output == 'zyx87'

    decoded = transformer.transform(
        TransformerRequest(
            text=encoded.output,
            decode=True,
            options={'type': 'letters'},
        ),
    )

    assert decoded.output == 'abc12'
    assert not transformer.transform(
        TransformerRequest(text=''),
    ).output


def test_caesar_cipher_shifts() -> None:
    """Verify shifting logic handles modular bounds accurately."""
    transformer = CaesarCipherTransformer()

    encoded = transformer.transform(
        TransformerRequest(
            text='abc',
            options={'shift': 1},
        ),
    )

    assert encoded.output == 'bcd'

    decoded = transformer.transform(
        TransformerRequest(
            text='bcd',
            decode=True,
            options={'shift': 1},
        ),
    )

    assert decoded.output == 'abc'

    identity = transformer.transform(
        TransformerRequest(
            text='abc',
            options={'shift': 62},
        ),
    )

    assert identity.output == 'abc'


def test_rail_fence_bounds() -> None:
    """Verify zigzag transpositions work correctly across keys."""
    transformer = RailFenceTransformer()
    message = 'WEAREDISCOVEREDFLEEATONCE'

    encoded = transformer.transform(
        TransformerRequest(
            text=message,
            options={'key': 3},
        ),
    )

    assert (
        transformer.transform(
            TransformerRequest(
                text=encoded.output,
                decode=True,
                options={'key': 3},
            ),
        ).output
        == message
    )

    assert not transformer.transform(
        TransformerRequest(
            text='',
            options={'key': 3},
        ),
    ).output


def test_morse_code_translation() -> None:
    """Verify Morse dictionary lookup paths."""
    transformer = MorseCodeTransformer()

    encoded = transformer.transform(
        TransformerRequest(text='sos'),
    )

    assert encoded.output == '... --- ...'

    decoded = transformer.transform(
        TransformerRequest(
            text='... --- ...',
            decode=True,
        ),
    )

    assert decoded.output == 'sos'

    encoded = transformer.transform(
        TransformerRequest(text='a b'),
    )

    assert encoded.output == '.- / -...'

    decoded = transformer.transform(
        TransformerRequest(
            text='.- / -...',
            decode=True,
        ),
    )

    assert decoded.output == 'a b'


def test_psc1_block_rotation() -> None:
    """Verify composite ROT13 processing and block flips."""
    transformer = Psc1Transformer()
    text = 'HELLOWORLD'

    encoded = transformer.transform(
        TransformerRequest(text=text),
    )

    decoded = transformer.transform(
        TransformerRequest(
            text=encoded.output,
            decode=True,
        ),
    )

    assert decoded.output == text
    assert not transformer.transform(
        TransformerRequest(text=''),
    ).output
