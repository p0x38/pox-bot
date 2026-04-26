from collections import Counter, defaultdict
import random
import time
from discord import Locale, app_commands
from discord.app_commands import locale_str

import data

class MyTranslator(app_commands.Translator):
    async def translate(self, string: locale_str, locale: Locale, context: app_commands.TranslationContext):
        translations = {
            'You do not have permission to use commands.': {
                'es-ES': 'No tienes permiso para usar comandos.',
                
            }
        }
        return translations.get(string.message, {}).get(locale.value, string.message)

class EmoticonGenerator:
    START_CHAR = '^'
    END_CHAR = '$'

    CORPUS = data.emoticons

    def __init__(self, corpus=None):
        self.corpus = corpus if corpus is not None else self.CORPUS
        self.model = self._build_model(self.corpus)
    
    def _build_model(self, corpus):
        model = defaultdict(Counter)

        for emoticon in corpus:
            current_state = self.START_CHAR

            for next_char in emoticon:
                model[current_state][next_char] += 1
                current_state = next_char
            
            model[current_state][self.END_CHAR] += 1
        
        return model
    
    def generate(self, max_length=8):
        current_char = self.START_CHAR
        new_emoticon = []

        for _ in range(max_length):
            if current_char not in self.model: break

            transitions = self.model[current_char]
            next_chars = list(transitions.keys())
            weights = list(transitions.values())

            next_char = random.choices(next_chars, weights=weights, k=1)[0]

            if next_char == self.END_CHAR: break

            new_emoticon.append(next_char)
            current_char = next_char
        
        return "".join(new_emoticon)
