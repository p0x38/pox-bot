import string
import textwrap

import data


def letter_reverser(input: str, decode: bool) -> str:
    alphabet = string.ascii_letters + string.digits
    reversed = alphabet[::-1]
    if decode == False:
        trans = str.maketrans(alphabet, reversed)
    else:
        trans = str.maketrans(reversed, alphabet)

    return input.translate(trans)

def caesar_cipher(input: str, shift: int, decode: bool) -> str:
    alphabet = string.ascii_letters + string.digits
    shift = shift % len(alphabet)

    if decode:
        shift = -shift
    
    shifted = alphabet[shift:] + alphabet[:shift]
    trans = str.maketrans(alphabet,shifted)

    return input.translate(trans)

def rail_fence(input: str, key):
    rails = [[] for _ in range(key)]
    rail_index = 0
    direction = 1

    for char in input:
        rails[rail_index].append(char)

        if rail_index == key - 1:
            direction = -1
        elif rail_index == 0:
            direction = 1
        
        rail_index += direction
    
    ciphered = ""

    for rail in rails:
        ciphered += "".join(rail)
    
    return ciphered

def decrypt_rail_fence(input, key):
    length = len(input)

    rail_map = [["\n"] * length for _ in range(key)]

    rail_index = 0
    direction = 1

    for i in range(length):
        rail_map[rail_index][i] = '*'
        if rail_index == key - 1 or rail_index == 0:
            direction *= -1
        rail_index += direction
    
    index = 0

    for r in range(key):
        for c in range(length):
            if rail_map[r][c] == '*':
                rail_map[r][c] = input[index]
                index += 1
    
    plain = ""
    rail_index = 0
    direction = 1

    for i in range(length):
        plain += rail_map[rail_index][i]
        if rail_index == key - 1 or rail_index == 0:
            direction *= -1
        rail_index += direction
    
    return plain

def morse_code(input: str, decode: bool = False):
    table = data.morse_code_table
    if decode:
        list2 = {}
        for k,v in table.items():
            list2[v] = k
        
        table = list2

        del list2
    result = []
    if not decode:
        for char in list(input):
            if char in table:
                result.append(table[char])
            elif char == " ":
                result.append("/")
            else:
                continue
        return " ".join(result)
    else:
        for code in input.split(" "):
            if code in table:
                result.append(table[code])
            elif code == "/":
                result.append(" ")
            else:
                continue
        return "".join(result)

def binary(input: str, decode: bool = False):
    if decode:
        clean = "".join(input.split())
        
        if len(input) % 8 != 0:
            clean = clean[:len(clean) - (len(clean) % 8)]
            if not clean: return ""

        chunks = textwrap.wrap(clean, 8)

        original = ''.join(chr(int(chunk, 2)) for chunk in chunks)
        return original
    else:
        chunks = [format(ord(char), '08b') for char in input]

        return ' '.join(chunks)

def psc1(input: str, decode: bool = False) -> str:
    output = ""

    if not decode:
        for char in input:
            if char.isupper():
                output += chr((ord(char) - 65 + 13) % 26 + 65)
            elif char.islower():
                output += chr((ord(char) - 97 + 13) % 26 + 97)
            else:
                output += char

        # reverse each chunks of 5 characters and loop back by -1 characters
        chunk_size = 5
        reversed_chunks = []
        for i in range(0, len(output), chunk_size):
            chunk = output[i:i + chunk_size]
            reversed_chunks.append(chunk[::-1])

        final_output = ''.join(reversed_chunks)
        return final_output
    else:
        # reverse each chunks of 5 characters and loop back by -1 characters
        chunk_size = 5
        reversed_chunks = []
        for i in range(0, len(input), chunk_size):
            chunk = input[i:i + chunk_size]
            reversed_chunks.append(chunk[::-1])

        reversed_input = ''.join(reversed_chunks)

        for char in reversed_input:
            if char.isupper():
                output += chr((ord(char) - 65 - 13) % 26 + 65)
            elif char.islower():
                output += chr((ord(char) - 97 - 13) % 26 + 97)
            else:
                output += char

        return output