import unicodedata

import numpy as np

from ..base_transformer import BaseTextTransformer
from ..constants import _UWU_RULES
from ..models import TransformerContext, TransformerRequest


class UwuTransformer(BaseTextTransformer):
    STUTTER_CHANCE = 0.879
    DEFAULT_FACES = np.array([':3', 'x3', '3:', '>:3'], dtype='<U3')
    DEFAULT_ACTIONS = np.array(
        [
            '*purrs*',
            '*mrrps*',
            '*wiggles ears*',
            '*nuzzles*',
        ],
    )

    def _apply_stutter(
        self,
        text: str,
        *,
        chance: float,
        max_words: int,
        max_repeats: int,
    ) -> str:
        words = text.split()
        stuttered = 0

        for i, word in enumerate(words):
            if not word:
                continue

            if word[0] in '@#:<#$!&/':
                continue

            if (
                stuttered >= max_words
                or not unicodedata.category(word[0]).startswith('L')
                or self.rng.random() >= chance
            ):
                continue

            repeat = int(self.rng.integers(1, max_repeats + 1))
            prefix = word[0]

            words[i] = f'{(prefix + "-") * repeat}{word}'
            stuttered += 1

        return ' '.join(words)

    def _transform(
        self,
        request: TransformerRequest,
        *,
        context: TransformerContext | None = None,
    ) -> str:
        text = request.text.lower()
        opts = request.options

        words = text.split()

        for i, word in enumerate(words):
            transformed = word

            if not transformed:
                continue

            if transformed[0] in '@#:<#$!&/':
                continue

            for pattern, replacement in _UWU_RULES:
                transformed = pattern.sub(replacement, transformed)

            words[i] = transformed

        text = ' '.join(words)

        if opts['stutter_chance']:
            text = self._apply_stutter(
                text,
                chance=opts['stutter_chance'],
                max_words=opts['stutter_max_words'],
                max_repeats=opts['stutter_max_repeats'],
            )

        return text

    @classmethod
    def parse_options(cls, **options):
        return {
            'lowercase': bool(options.get('lowercase', True)),
            'stutter_chance': float(options.get('stutter_chance', 0.88)),
            'stutter_max_words': max(1, int(options.get('stutter_max_words', 3))),
            'stutter_max_repeats': max(1, int(options.get('stutter_max_repeats', 3))),
            'faces': bool(options.get('faces', True)),
            'face_chance': float(options.get('face_chance', 0.15)),
            'face_pool': tuple(options.get('face_pool', cls.DEFAULT_FACES)),
            'actions': bool(options.get('actions')),
            'action_chance': float(options.get('action_chance', 0.05)),
            'action_pool': tuple(options.get('action_pool', cls.DEFAULT_ACTIONS)),
            'regex_rules': tuple(options.get('regex_rules', _UWU_RULES)),
            'preserve_mentions': bool(options.get('preserve_mentions', True)),
            'preserve_urls': bool(options.get('preserve_urls', True)),
            'preserve_code': bool(options.get('preserve_code', True)),
        }
