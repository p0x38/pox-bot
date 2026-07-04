import pytest
from src.utils._ciphers.hill import hill_cipher, is_valid_hill_key


@pytest.fixture
def valid_matrix():
    """Return an invertible 2x2 modular matrix (determinant coprime to 26)."""
    return [[3, 3], [2, 5]]


@pytest.fixture
def invalid_matrix():
    """Return a matrix whose modular determinant is not coprime to 26."""
    return [[2, 4], [1, 2]]


def test_hill_key_validation(valid_matrix, invalid_matrix):
    """Verify key validator handles invertibility correctly."""
    assert is_valid_hill_key(valid_matrix) is True
    assert is_valid_hill_key(invalid_matrix) is False
    assert is_valid_hill_key([[1]]) is False


def test_hill_cipher_execution(valid_matrix, invalid_matrix):
    """Verify matrix operations execute modulo 26 blocks."""
    message = 'HELP'
    encoded = hill_cipher(message, valid_matrix)

    assert hill_cipher(encoded, valid_matrix, decode=True) == message

    with pytest.raises(ValueError, match='Key matrix is not invertible'):
        hill_cipher('DATA', invalid_matrix, decode=True)
