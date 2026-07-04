from src.utils._ciphers.classical import (
    caesar_cipher,
    morse_code,
    psc1,
    rail_fence,
    reverse_letter,
)


def test_reverse_letter_cipher():
    """Verify alphanumeric mirroring via lookup tables."""
    assert reverse_letter('abc12') == '987ih'
    assert reverse_letter('987ih', decode=True) == 'abc12'
    assert reverse_letter('') == ''


def test_caesar_cipher_shifts():
    """Verify shifting logic handles modular bounds accurately."""
    assert caesar_cipher('abc', shift=1) == 'bcd'
    assert caesar_cipher('bcd', shift=1, decode=True) == 'abc'
    assert (
        caesar_cipher(
            'abc',
            shift=len('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'),
        )
        == 'abc'
    )


def test_rail_fence_bounds():
    """Verify zigag transpositions work correctly across keys."""
    message = 'WEAREDISCOVEREDFLEEATONCE'
    encoded = rail_fence(message, key=3)

    assert rail_fence(encoded, key=3, decode=True) == message

    assert rail_fence('test', key=1) == 'test'
    assert rail_fence('', key=3) == ''


def test_morse_code_translation():
    """Verify Morse dictionary lookup paths."""
    assert morse_code('sos') == '... --- ...'
    assert morse_code('... --- ...', decode=True) == 'sos'

    assert morse_code('a b') == '.- / -...'
    assert morse_code('.- / -...', decode=True) == 'a b'


def test_psc1_block_rotation():
    """Verify composite ROT13 processing and block flips."""
    text = 'HELLOWORLD'
    encoded = psc1(text)

    assert psc1(encoded, decode=True) == text
    assert psc1('') == ''
