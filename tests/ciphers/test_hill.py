import pytest

from poxbot.features.text_transform.models import TransformerRequest
from poxbot.features.text_transform.transformers.hill import HillCipherTransformer
from poxbot.shared.exceptions.text_transform import InvalidKeyError


@pytest.fixture
def valid_matrix() -> list[list[int]]:
    """Return an invertible 2x2 modular matrix."""
    return [[3, 3], [2, 5]]


@pytest.fixture
def invalid_matrix() -> list[list[int]]:
    """Return a matrix whose modular determinant is not coprime to 26."""
    return [[2, 4], [1, 2]]


def test_hill_key_validation(
    valid_matrix: list[list[int]],
    invalid_matrix: list[list[int]],
) -> None:
    """Verify key validation handles invertibility correctly."""
    transformer = HillCipherTransformer()

    assert transformer.is_valid_key(valid_matrix) is True
    assert transformer.is_valid_key(invalid_matrix) is False
    assert transformer.is_valid_key([[1]]) is False


def test_hill_cipher_execution(
    valid_matrix: list[list[int]],
    invalid_matrix: list[list[int]],
) -> None:
    """Verify matrix operations execute modulo 26 blocks."""
    transformer = HillCipherTransformer()
    message = 'HELP'

    encoded = transformer.transform(
        TransformerRequest(
            text=message,
            options={'key_matrix': valid_matrix},
        ),
    )

    decoded = transformer.transform(
        TransformerRequest(
            text=encoded.output,
            decode=True,
            options={'key_matrix': valid_matrix},
        ),
    )

    assert decoded.output == message

    with pytest.raises(InvalidKeyError):
        transformer.transform(
            TransformerRequest(
                text='DATA',
                decode=True,
                options={'key_matrix': invalid_matrix},
            ),
        )
