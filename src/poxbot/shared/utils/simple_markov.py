from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from random import Random
from typing import ClassVar


class MarkovStatusGenerator:
    """
    Variable-order Markov generator for short statuses.

    Supports:
    - English and other space-separated text.
    - Japanese morphological tokenization through fugashi.
    - Character-level Japanese fallback without extra dependencies.
    - Mixed Japanese and English.
    - Frequency-weighted sampling.
    - Variable-order context backoff.
    - Temperature-controlled randomness.
    - Optional n-gram repetition prevention.

    When fugashi is unavailable, Japanese text is tokenized by character.
    In that mode, min_words and max_words count Japanese characters rather
    than linguistic words.
    """

    _BEGIN = '\0BEGIN'
    _END = '\0END'

    _JAPANESE_CHAR = (
        r'\u3040-\u30ff'
        r'\u3400-\u4dbf'
        r'\u4e00-\u9fff'
        r'\uF900-\uFAFF'
        r'々〆ヵヶー'
    )

    _JAPANESE_SPAN_RE = re.compile(rf'[{_JAPANESE_CHAR}]+')

    _JAPANESE_CHAR_RE = re.compile(rf'[{_JAPANESE_CHAR}]')

    # ruff: ignore[ambiguous-unicode-character-string]
    _TOKEN_RE = re.compile(
        r'<3'
        r"|(?:[:;=8Xx][-^']?[)(/DdPp3])"
        r"|[A-Za-z0-9_]+(?:['’][A-Za-z0-9_]+)*"
        rf'|[{_JAPANESE_CHAR}]+'
        r"|[^\W\d_]+(?:['’][^\W\d_]+)*"
        r'|[^\s]',
        re.UNICODE,
    )

    # ruff: ignore[ambiguous-unicode-character-string]
    _NO_SPACE_BEFORE: ClassVar[set] = set(
        '.,!?;:%)]}…。，、？！。；：」』）】〉》〕］｝”’'
    )

    _NO_SPACE_AFTER: ClassVar[set] = set('([{「『（【〈《〔［｛“‘')  # ruff: ignore[ambiguous-unicode-character-string]

    def __init__(
        self,
        order: int = 2,
        *,
        seed: int | None = None,
    ) -> None:
        if order < 1:
            raise ValueError('order must be at least 1')

        self.order = order
        self._rng = Random(seed)

        self._transitions: defaultdict[
            tuple[str, ...],
            Counter[str],
        ] = defaultdict(Counter)

        self._sentence_count = 0

        # Japanese morphological tokenization is optional.
        # The generator still works without fugashi.
        self._japanese_tagger = None

        try:
            # ruff: ignore[import-outside-top-level]
            from fugashi import Tagger  # pyright: ignore[reportAttributeAccessIssue]

            self._japanese_tagger = Tagger()
        except (ImportError, RuntimeError, OSError, ValueError):
            pass

    @staticmethod
    def _contains_japanese(token: str) -> bool:
        return bool(MarkovStatusGenerator._JAPANESE_CHAR_RE.search(token))

    def _tokenize(self, text: str) -> list[str]:
        """
        Tokenize text while preserving punctuation and emoticons.

        Japanese spans use fugashi when available, or individual
        characters as a dependency-free fallback.
        """
        tokens: list[str] = []

        for raw_token in self._TOKEN_RE.findall(text):
            if self._JAPANESE_SPAN_RE.fullmatch(raw_token):
                if self._japanese_tagger is not None:
                    tokens.extend(
                        word.surface for word in self._japanese_tagger(raw_token)
                    )
                else:
                    tokens.extend(raw_token)

            else:
                tokens.append(raw_token)

        return tokens

    @classmethod
    def _is_word(cls, token: str) -> bool:
        """Return whether a token contributes to the length limit."""
        return any(character.isalnum() for character in token)

    @classmethod
    def _detokenize(cls, tokens: list[str]) -> str:
        """
        Reconstruct text with script-aware spacing.

        English words receive spaces. Japanese tokens are joined without
        spaces, while punctuation stays attached to the appropriate text.
        """
        if not tokens:
            return ''

        output = ''
        previous = ''
        quote_open = False

        for token in tokens:
            if not output:
                output = token

            elif token == '"':
                if quote_open:
                    # Closing quote.
                    output += token
                else:
                    # Opening quote.
                    if previous and previous not in cls._NO_SPACE_AFTER:
                        output += ' '

                    output += token

                quote_open = not quote_open

            elif (
                token in cls._NO_SPACE_BEFORE
                or previous in cls._NO_SPACE_AFTER
                or (previous == '"' and quote_open)
                or (cls._contains_japanese(previous) and cls._contains_japanese(token))
            ):
                output += token

            else:
                output += ' ' + token

            previous = token

        return output.strip()

    def train(self, sentences: Iterable[str]) -> None:
        """
        Train on statuses or sentences.

        Calling train again replaces the existing model.
        """
        self._transitions.clear()
        self._sentence_count = 0

        for sentence in sentences:
            if not sentence or not sentence.strip():
                continue

            tokens = self._tokenize(sentence)

            if not tokens:
                continue

            self._sentence_count += 1

            sequence = [self._BEGIN] * self.order + tokens + [self._END]

            for index in range(self.order, len(sequence)):
                next_token = sequence[index]

                # Learn every available context size. Shorter contexts
                # provide backoff when a longer context is unknown.
                for context_size in range(1, self.order + 1):
                    context = tuple(sequence[index - context_size : index])

                    self._transitions[context][next_token] += 1

    def _get_transitions(
        self,
        history: list[str],
    ) -> Counter[str] | None:
        """Use the longest available context, backing off as needed."""
        for context_size in range(
            min(self.order, len(history)),
            0,
            -1,
        ):
            context = tuple(history[-context_size:])
            transitions = self._transitions.get(context)

            if transitions:
                return transitions

        return None

    def _weighted_choice(
        self,
        transitions: Counter[str],
        temperature: float,
    ) -> str:
        """Sample an observed transition using its frequency."""
        items = list(transitions.items())
        max_count = max(count for _, count in items)

        exponent = 1.0 / temperature

        tokens = [token for token, _ in items]
        weights = [(count / max_count) ** exponent for _, count in items]

        return self._rng.choices(
            tokens,
            weights=weights,
            k=1,
        )[0]

    @staticmethod
    def _repeats_ngram(
        generated: list[str],
        candidate: str,
        n: int,
    ) -> bool:
        """Check whether a candidate would repeat an existing n-gram."""
        combined = [*generated, candidate]

        if len(combined) < n:
            return False

        target = tuple(combined[-n:])

        return any(
            tuple(combined[index : index + n]) == target
            for index in range(len(combined) - n)
        )

    def generate(
        self,
        *,
        min_words: int = 3,
        max_words: int = 14,
        temperature: float = 0.9,
        no_repeat_ngram_size: int = 3,
    ) -> str:
        """
        Generate a status.

        Args:
            min_words:
                Minimum desired number of word-like tokens.

            max_words:
                Maximum number of word-like tokens.

            temperature:
                Lower values favor frequent transitions.
                Higher values increase variation.

            no_repeat_ngram_size:
                Avoid repeated sequences of this many tokens.
                Values of 0 or 1 disable repetition filtering.
        """
        if self._sentence_count == 0:
            raise RuntimeError('Train the generator before generating statuses.')

        if min_words < 0:
            raise ValueError('min_words cannot be negative')

        if max_words < 1:
            raise ValueError('max_words must be at least 1')

        if min_words > max_words:
            raise ValueError('min_words cannot exceed max_words')

        if not math.isfinite(temperature) or temperature <= 0:
            raise ValueError('temperature must be finite and greater than 0')

        if no_repeat_ngram_size < 0:
            raise ValueError('no_repeat_ngram_size cannot be negative')

        history = [self._BEGIN] * self.order
        generated: list[str] = []
        word_count = 0

        max_steps = max(32, max_words * 4 + self.order * 2)

        for _ in range(max_steps):
            transitions = self._get_transitions(history)

            if not transitions:
                break

            choices = dict(transitions)

            # Avoid ending before the requested minimum length,
            # provided another transition is available.
            if word_count < min_words and len(choices) > 1:
                without_end = {
                    token: count
                    for token, count in choices.items()
                    if token != self._END
                }

                if without_end:
                    choices = without_end

            # After reaching the limit, allow only punctuation or ending.
            if word_count >= max_words:
                terminal_choices = {
                    token: count
                    for token, count in choices.items()
                    if (token == self._END or not self._is_word(token))
                }

                if terminal_choices:
                    choices = terminal_choices
                else:
                    break

            # Avoid repeated n-grams when alternatives exist.
            if no_repeat_ngram_size >= 2 and len(choices) > 1:
                filtered_choices = {
                    token: count
                    for token, count in choices.items()
                    if (
                        token == self._END
                        or not self._repeats_ngram(
                            generated,
                            token,
                            no_repeat_ngram_size,
                        )
                    )
                }

                if filtered_choices:
                    choices = filtered_choices

            next_token = self._weighted_choice(
                Counter(choices),
                temperature,
            )

            if next_token == self._END:
                break

            generated.append(next_token)

            if self._is_word(next_token):
                word_count += 1

            history.append(next_token)

            if len(history) > self.order:
                history = history[-self.order :]

        return self._detokenize(generated)
