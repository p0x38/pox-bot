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
        # --- SPECIFIED WORDS --- #
        (r'\byou\b', 'u'),
        (r'\btime\b', 'tim'),
        (r'^me$', 'mwe'),
        (r'hey', 'hay'),
        (r'dead', 'ded'),
        (r'when', 'wen'),
        (r'meme', 'mem'),
        (r'the', 'teh'),
        (r'that', 'dat'),
        (r'great', 'gwate'),
        (r'remember', 'rember'),
        (r'frightened?', 'fwigten'),
        (r'worse', 'wose'),
        
        # --- R / L Rules --- #
        (r'th(?!e)', 'f'),
        (r'fi', 'fwi'),
        (r'poi', 'pwoi'),
        (r'avait', 'await'),
        (r'dedicat', 'deditat'),
        (r'feel$', 'fell'),
        (r'ol', 'owl'),
        (r'ry', 'wwy'),
        (r'ly', 'wy'),
        (r'([b-df-hj-np-tv-z])le$', r'\1wal'),
        
        # --- Phonemes & Vowels Rules --- #
        (r'n[aeiou]*t', 'nd'),
        (r'fuc', 'fwuc'),
        (r'mem', 'mwem'),
        (r'mom', 'mwom'),
        (r'nywo', 'nyo'),
        (r'ove', 'uv'),
        (r'n([aeiou])', r'ny\1'),
        (r'([^aeiou\s])o', r'\1wo'),
        
        # --- Convert remaining R and L into W --- #
        (r'[lrw]+', 'w'),
        
        # --- Aggregation of Laughter --- #
        (r'\b(?:ha|hah|heh|hehe)+\b', 'hehe'),
        
        # --- UwU-ify emoticons --- #
        (r'([><:;=\']*)?[xX]+[dD]+', r'\1x3'),
        (r'([><:;=\'_]+)-?[\)\]\>]+', r'\13'),
        (r'[\(\[\<]+-?([><:;=\'_]+)', r'3:\1'),
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
