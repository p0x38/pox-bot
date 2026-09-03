from __future__ import annotations


class TextTransformError(Exception):
    """Base exception for all text transformer pipeline errors."""


class CipherError(TextTransformError):
    """Mixin category for traditional cryptographic ciphers (e.g., Hill, Caesar)."""


class AlgorithmError(TextTransformError):
    """Mixin category for algorithmic or structural distortions (e.g., Automata)."""


class NoTextTransformerObjectError(TextTransformError):
    """Exception raised when a requested transformer does not exist."""

    def __init__(self, *args: object) -> None:
        super().__init__("The transformer doesn't exist", *args)


class TransformerArgumentError(TextTransformError):
    """Base exception for missing, malformed, or invalid configuration arguments."""

    def __init__(self, *args: object) -> None:
        msg = 'Required transformer configuration argument is missing.'
        super().__init__(msg, *args)


class TextDecodeError(TextTransformError):
    """Base exception for payloads that are mathematically impossible to decode."""

    def __init__(self, *args: object) -> None:
        msg = 'The provided text structure is corrupt and cannot be decoded.'
        super().__init__(msg, *args)


class NoArgumentError(TransformerArgumentError):
    """Exception raised when kwargs dictionary is completely empty but required."""

    def __init__(self, *args: object) -> None:
        msg = 'No configuration arguments were supplied to the transformer.'
        super().__init__(msg, *args)


class MissingKeyMatrixError(TransformerArgumentError, CipherError):
    """Exception raised when the required key_matrix parameter is missing."""

    def __init__(self, *args: object) -> None:
        msg = 'key_matrix parameter is required for Hill Cipher.'
        super().__init__(msg, *args)


class InvalidKeyError(TransformerArgumentError, CipherError):
    """Exception raised when an encryption key matrix is mathematically invalid."""

    def __init__(self, *args: object) -> None:
        msg = 'The provided encryption key matrix is invalid.'
        super().__init__(msg, *args)


class InvalidCaesarShiftError(TransformerArgumentError, CipherError):
    """Exception raised when the Caesar cipher shift value is malformed."""

    def __init__(self, *args: object) -> None:
        msg = 'Caesar shift parameter must be a valid non-zero integer.'
        super().__init__(msg, *args)


class InvalidRailFenceKeyError(TransformerArgumentError, CipherError):
    """Exception raised when the rail fence rail count is lower than 2."""

    def __init__(self, *args: object) -> None:
        msg = 'Rail fence cipher requires a rail key count of 2 or more.'
        super().__init__(msg, *args)


class CellularAutomataArgumentError(TransformerArgumentError, AlgorithmError):
    """Exception raised when generations or ruleset values are invalid."""

    def __init__(self, *args: object) -> None:
        msg = 'Cellular automata generation count or ruleset is invalid.'
        super().__init__(msg, *args)


class InvalidGlitchRateError(TransformerArgumentError, AlgorithmError):
    """Exception raised when the void corruption rate is outside [0.0, 1.0]."""

    def __init__(self, *args: object) -> None:
        msg = 'Glitch rate must be a floating-point value between 0.0 and 1.0.'
        super().__init__(msg, *args)


class InvalidSeedKeyError(TransformerArgumentError, AlgorithmError):
    """Exception raised when the image scramble seed key is malformed."""

    def __init__(self, *args: object) -> None:
        msg = 'The scramble seed_key must be a valid integer parameter.'
        super().__init__(msg, *args)


class InvalidBlockSizeError(TransformerArgumentError, AlgorithmError):
    """Exception raised when a block or chunk split size is lower than 1."""

    def __init__(self, *args: object) -> None:
        msg = 'Block or chunk split size must be an integer greater than zero.'
        super().__init__(msg, *args)


class InvalidMockingTypeError(TransformerArgumentError, AlgorithmError):
    """Exception raised when the mocking sequence type is unsupported."""

    def __init__(self, *args: object) -> None:
        msg = 'The requested mocking sequence type pattern is not recognized.'
        super().__init__(msg, *args)


class BinaryDecodeError(TextDecodeError, AlgorithmError):
    """Exception raised when binary string contains non-binary elements."""

    def __init__(self, *args: object) -> None:
        msg = 'The text payload contains invalid characters for binary decoding.'
        super().__init__(msg, *args)


class InvalidMorseTokenError(TextDecodeError, CipherError):
    """Exception raised when encountering an unknown token during Morse decoding."""

    def __init__(self, *args: object) -> None:
        msg = 'Found an invalid or unregistered token while decoding Morse code.'
        super().__init__(msg, *args)
