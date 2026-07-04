from src.utils._ciphers.masking import cellular_automata_mask


def test_cellular_automata_masking():
    """Verify Conway rules introduce structural masks successfully."""
    secret = 'Confidential Information'
    masked = cellular_automata_mask(secret, generations=2)
    assert masked != secret
