from __future__ import annotations

import re
import string
from typing import Final

import numpy as np
from numpy.typing import NDArray

MORSE_CODE_TABLE: Final[dict[str, str]] = {
    'a': '.-',
    'b': '-...',
    'c': '-.-.',
    'd': '-..',
    'e': '.',
    'f': '..-.',
    'g': '--.',
    'h': '....',
    'i': '..',
    'j': '.---',
    'k': '-.-',
    'l': '.-..',
    'm': '--',
    'n': '-.',
    'o': '---',
    'p': '.--.',
    'q': '--.-',
    'r': '.-.',
    's': '...',
    't': '-',
    'u': '..-',
    'v': '...-',
    'w': '.--',
    'x': '-..-',
    'y': '-.--',
    'z': '--..',
    '0': '-----',
    '1': '.----',
    '2': '..---',
    '3': '...--',
    '4': '....-',
    '5': '.....',
    '6': '-....',
    '7': '--...',
    '8': '---..',
    '9': '----.',
    '&': '.-...',
    "'": '.----.',
    '@': '.--.-.',
    ')': '-.--.-',
    '(': '-.--.',
    ':': '---...',
    ',': '--..--',
    '=': '-...-',
    '!': '-.-.--',
    '.': '.-.-.-',
    '-': '-....-',
    '%': '-..-',
    '+': '.-.-.',
    '"': '.-..-.',
    '?': '..--..',
    '\n': '.-.-',
    '<SOS>': '...---...',
}
_UWU_RULES = tuple(
    (re.compile(pattern), replacement)
    for pattern, replacement in [
        (r'hey', 'hay'),
        (r'dead', 'ded'),
        (r'n[aeiou]*t', 'nd'),
        (r'read', 'wead'),
        (r'that', 'dat'),
        (r'th(?!e)', 'f'),
        (r've', 'we'),
        (r'le$', 'wal'),
        (r'ry', 'wwy'),
        (r'[rw]', 'w'),
        (r'll', 'w'),
        (r'[aeiur]l$', 'wl'),
        (r'ol', 'owl'),
        (r'[lr]o', 'wo'),
        (r'([bcdfghjkmnpqstxyz])o', '\\1wo'),
        (r'[vw]le', 'wal'),
        (r'fi', 'fwi'),
        (r'ver', 'wer'),
        (r'poi', 'pwoi'),
        (r'(?:dfghjpqrstxyz)le$', '\\1wal'),
        (r'ly', 'wy'),
        (r'ple', 'pwe'),
        (r'nr', 'nw'),
        (r'mem', 'mwem'),
        (r'nywo', 'nyo'),
        (r'fuc', 'fwuc'),
        (r'mom', 'mwom'),
        (r'^me$', 'mwe'),
        (r'n(?:[aeiou])', 'ny\\1'),
        (r'ove', 'uv'),
        (r'\b(?:ha|hah|heh|hehe)+\b', 'hehe'),
        (r'the', 'teh'),
        (r'\byou\b', 'u'),
        (r'\btime\b', 'tim'),
        (r'over', 'ower'),
        (r'worse', 'wose'),
        (r'great', 'gwate'),
        (r'aviat', 'awiat'),
        (r'dedicat', 'deditat'),
        (r'remember', 'rember'),
        (r'when', 'wen'),
        (r'frighten(ed)*', '\\1rigten'),
        (r'meme', 'mem'),
        (r'feel$', 'fell'),
        (r'(?:[<>])?[:;=\'_]+-?[\)\]\>]+', "\\1:3"),
        (r'[<\[\(]+-?[:;=\'_]+(?:[<>])?', "\\1:3"),
        (r'(?:[>])?[:;=\'_]+-?[\(\[\<]+', "3:\\1"),
        (r'[>?\]\)]+-?[:;=\'_]+(?:[<>])?', "3:\\1"),
        (r'(?:[><])?[xX:;=\']+[dD]+', "\\1x3"),
        (r'[dD]+[xX:;=\']+(?:[><])?', "\\1x3"),
    ]
)
ALPHA_STR: Final[str] = string.ascii_letters + string.digits
ALPHA_ARR: Final[NDArray[np.uint8]] = np.frombuffer(
    ALPHA_STR.encode('ascii'), dtype=np.uint8,
)
REV_ALPHA_ARR: Final[NDArray[np.uint8]] = ALPHA_ARR[::-1]

ENCODE_LOOKUP: Final[NDArray[np.uint8]] = np.arange(256, dtype=np.uint8)
ENCODE_LOOKUP[ALPHA_ARR] = REV_ALPHA_ARR

DECODE_LOOKUP: Final[NDArray[np.uint8]] = np.arange(256, dtype=np.uint8)
DECODE_LOOKUP[REV_ALPHA_ARR] = ALPHA_ARR
