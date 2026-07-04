from src.utils._ciphers.image import image_glitch_scramble


def test_image_glitch_scramble_vectors():
    """Verify matrix roll behavior matches seeded pseudo-random lines."""
    payload = 'COMPUTERSCIENCE'
    seed = 1337
    scrambled = image_glitch_scramble(payload, seed_key=seed)

    assert scrambled != payload
    assert image_glitch_scramble(scrambled, seed_key=seed, decode=True) == payload


def test_image_glitch_short_inputs():
    """Ensure short inputs pass untouched without throwing indexing errors."""
    assert image_glitch_scramble('abc', seed_key=42) == 'abc'
