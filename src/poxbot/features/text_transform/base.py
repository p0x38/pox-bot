from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def ascii_to_ndarray(text: str) -> NDArray[np.uint8]:
    """Convert an ASCII string into a NumPy uint8 array."""
    return np.frombuffer(
        text.encode('ascii', errors='replace'),
        dtype=np.uint8,
    )


def ndarray_to_ascii(array: NDArray[np.uint8]) -> str:
    """Convert a NumPy uint8 array back into an ASCII string."""
    return array.tobytes().decode('ascii')


def get_integer_adjugate(
    matrix: NDArray[np.int_],
) -> NDArray[np.int_]:
    """Compute the exact integer adjugate matrix."""
    size = matrix.shape[0]
    adjugate = np.zeros_like(matrix, dtype=int)

    for row in range(size):
        for col in range(size):
            rows = np.array(
                [i for i in range(size) if i != row],
                dtype=int,
            )
            cols = np.array(
                [i for i in range(size) if i != col],
                dtype=int,
            )

            minor = matrix[rows[:, None], cols]

            determinant = (
                int(np.round(np.linalg.det(minor))) if size > 2 else int(minor[0, 0])
            )

            adjugate[col, row] = determinant if (row + col) % 2 == 0 else -determinant

    return adjugate
