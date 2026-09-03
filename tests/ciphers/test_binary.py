from poxbot.features.text_transform.models import TransformerRequest
from poxbot.features.text_transform.transformers.binary import BinaryTransformer


def test_binary_encode_and_decode() -> None:
    """Verify that text cleanly converts to bit strings and back."""
    transformer = BinaryTransformer()
    secret = 'Hello'

    encoded = transformer.transform(
        TransformerRequest(text=secret),
    )

    assert '01001000' in encoded.output

    decoded = transformer.transform(
        TransformerRequest(text=encoded.output, decode=True),
    )

    assert decoded.output == secret


def test_binary_empty_or_malformed() -> None:
    """Verify handling of empty or padding-corrupted inputs."""
    transformer = BinaryTransformer()

    assert not transformer.transform(
        TransformerRequest(text=''),
    ).output

    assert not transformer.transform(
        TransformerRequest(text='', decode=True),
    ).output

    assert (
        transformer.transform(
            TransformerRequest(
                text='01001000   01101001',
                decode=True,
            ),
        ).output
        == 'Hi'
    )
