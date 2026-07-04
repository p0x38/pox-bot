from src.utils._ciphers.binary import binary


def test_binary_encode_and_decode():
    """Verify that text cleanly converts to bit strings and back."""
    secret = 'Hello'
    encoded = binary(secret)

    assert '01001000' in encoded

    decoded = binary(encoded, decode=True)
    assert decoded == secret


def test_binary_empty_or_malformed():
    """Verify handling of empty or padding-corrupted inputs."""
    assert binary('') == ''
    assert binary('', decode=True) == ''

    assert binary('01001000   01101001', decode=True) == 'Hi'
