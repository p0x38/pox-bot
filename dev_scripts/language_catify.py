import json
import random
import re
from pathlib import Path


def get_case_pattern(word):
    return [char.isupper() for char in word]


def apply_case_pattern(word, pattern):
    new_word = ''
    for i, char in enumerate(word):
        if i < len(pattern) and pattern[i]:
            new_word += char.upper()
        else:
            new_word += char.lower()
    return new_word


def to_meow_weighted(word):
    if not word or not any(c.isalpha() for c in word):
        return word

    # Skip common emoticons and short special strings
    if re.match(r'^[:;=xX8][\-~]?[\)\]\(\[DdPpoO3> <]+$', word):
        return word

    numberd = [0, 1, 2]
    weightgg = [50, 2, 1]
    ran = random.choices(numberd, weights=weightgg)[0]
    length = len(word)
    case_pattern = get_case_pattern(word)

    if length <= 3:
        return apply_case_pattern(random.choice(['maw', 'mew', 'mow']), case_pattern)

    weights = {'m': 3, 'e': 3, 'i': 3, 'o': 3, 'a': 3, 'w': 3}
    total_weight = sum(weights.values())

    match ran:
        case 0:
            chars = ('m', 'e', 'o', 'w')
        case 1:
            chars = ('m', 'i', 'a', 'w')
        case 2:
            chars = ('m', 'a', 'o', 'w')
        case _:
            chars = ('m', 'e', 'o', 'w')

    counts = [round(length * (weights[c] / total_weight)) for c in chars]
    diff = length - sum(counts)
    counts[1] += diff

    meow_word = ''.join(chars[i] * max(1, counts[i]) for i in range(4))
    return apply_case_pattern(meow_word, case_pattern)


def meow_phrase_weighted(phrase):
    final_phrase = ''
    current_word = ''

    for char in phrase:
        if char.isalpha():
            current_word += char
        else:
            if current_word:
                final_phrase += to_meow_weighted(current_word)
                current_word = ''
            final_phrase += char

    if current_word:
        final_phrase += to_meow_weighted(current_word)

    return final_phrase


def process_value(value):
    if isinstance(value, str):
        parts = re.split(r'(\{[^{}]+\}|[:;=xX8][\-~]?[\)\]\(\[DdPpoO3> <]+)', value)

        processed_parts = []
        for p in parts:
            if not p:
                continue
            if p.startswith('{') or re.match(
                r'^[:;=xX8][\-~]?[\)\]\(\[DdPpoO3> <]+$', p
            ):
                processed_parts.append(p)
            else:
                processed_parts.append(meow_phrase_weighted(p))

        return ''.join(processed_parts)

    if isinstance(value, dict):
        return {k: process_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [process_value(v) for v in value]
    return value


def catify_files():
    base_path = Path('resources/locales/en')
    out_path = Path('resources/locales/cat')

    if not out_path.exists():
        out_path.mkdir(parents=True)

    for json_file in base_path.glob('*.json'):
        print(f'🐾 Meow-ifying {json_file.name}...')
        with Path(json_file).open('r', encoding='utf-8') as f:
            data = json.load(f)

        cat_data = process_value(data)

        with Path(out_path / json_file.name).open('w', encoding='utf-8') as f:
            json.dump(cat_data, f, indent=4, ensure_ascii=False)

    print('✨ Purr-fect! All files converted to Meow language. >:D')


if __name__ == '__main__':
    catify_files()
