from __future__ import annotations

import math

import numpy as np

from ....shared.exceptions.text_transform import (
    InvalidKeyError,
    MissingKeyMatrixError,
)
from ..base import get_integer_adjugate
from ..base_transformer import BaseTextTransformer
from ..models import TransformerContext, TransformerRequest


class HillCipherTransformer(BaseTextTransformer):
    """Classic Hill cipher with matrix-based text encoding and decoding."""

    def is_valid_key(self, key_matrix: list[list[int]]) -> bool:
        """Verify if the key matrix is invertible modulo 26.

        Args:
            key_matrix (list[list[int]]): Square matrix to check.

        Returns:
            bool: True if determinant is coprime to 26.
        """
        matrix = np.asarray(key_matrix, dtype=int)
        if (
            matrix.ndim != 2
            or matrix.shape[0] != matrix.shape[1]
            or matrix.shape[0] < 2
        ):
            return False
        determinant = int(np.round(np.linalg.det(matrix)))
        return math.gcd(determinant, 26) == 1

    def _transform(
        self,
        request: TransformerRequest,
        *,
        context: TransformerContext | None = None,
    ) -> str:
        """Encrypt or decrypt alphabetic text using Hill Matrix multiplication."""
        text = request.text
        key_matrix = request.options.get('key_matrix')
        pad_char = request.options.get('pad_char', 'X').upper()[:1] or 'X'

        if key_matrix is None:
            raise MissingKeyMatrixError()

        if not self.is_valid_key(key_matrix):
            raise InvalidKeyError()

        clean = ''.join(c.upper() for c in text if c.isalpha())
        if not clean:
            return text

        size = len(key_matrix)
        clean += pad_char * ((size - len(clean) % size) % size)
        matrix = np.asarray(key_matrix, dtype=int)

        if request.decode:
            determinant = int(np.round(np.linalg.det(matrix))) % 26
            inverse = pow(determinant, -1, 26)
            matrix = (inverse * get_integer_adjugate(matrix)) % 26

        blocks = np.fromiter((ord(c) - 65 for c in clean), dtype=int).reshape(-1, size)
        transformed_blocks = (blocks @ matrix.T) % 26
        return ''.join(chr(num + 65) for num in transformed_blocks.ravel())

    @classmethod
    def parse_options(cls, **options):
        matrix = options.get('key_matrix')
        if matrix is None:
            raise MissingKeyMatrixError()

        if isinstance(matrix, str):
            matrix = [[int(v) for v in row.split(',')] for row in matrix.split(';')]

        return {
            'key_matrix': matrix,
            'pad_char': str(options.get('pad_char', 'X'))[:1],
        }
