# 🪄 pox-bot Inline Text Processing DSL

> [!Note]
> Generated with Gemini cuz I was lazy to make documentation of that :P

Welcome to the dynamic text processing module of pox-bot! 
This module allows you to freely hack and manipulate text character-by-character using a safely sandboxed, **Python-like custom Domain-Specific Language (DSL)**.

## 📌 1. Basic Mechanics

This DSL evaluates your expression against **each character** of the input text in a loop.
The result (return value) of your expression determines how that specific character is processed.

* **Returning a Boolean (True/False):**
  * `True` ➡ Keep the character as-is (`'keep'`)
  * `False` ➡ Delete the character (`'delete'`)
* **Returning Specific Reserved Keywords (Strings):**
  * Special actions are triggered if you return exactly: `'upper'`, `'lower'`, `'reverse'`, `'delete'`, or `'keep'`.
* **Returning Other Strings:**
  * Any other string is injected inline as "replacement text". (This allows for character multiplication, or replacing characters with entire words or emojis!)

---

## 📊 2. Available Context Variables

During evaluation, the following variables are automatically injected into the context for you to use on each character.

| Variable | Shortcut | Type | Description |
| :--- | :--- | :--- | :--- |
| `char` | `c` | `str` | The character currently being evaluated (length of 1). |
| `index` | `idx` | `int` | The index of the current character (0-indexed). |
| `rev_idx` | - | `int` | The reverse index from the end (last character is `0`). |
| `word_idx` | - | `int` | The index of the character within the current space-separated word. |
| `prev_char` | - | `str` | The previous character (empty string `''` if at the start). |
| `next_char` | - | `str` | The next character (empty string `''` if at the end). |
| `text_before`| - | `str` | The entire string before the current character. |
| `text_after` | - | `str` | The entire string after the current character. |
| `total_len` | - | `int` | The total number of characters in the input text. |
| `code` | - | `int` | The ASCII/Unicode code point of the current character (`ord(char)`). |

### 🚩 Condition Flags (Booleans)
These handy flags are pre-calculated for easy `if` conditions:
* `is_alpha` : `True` if it's an alphabet letter.
* `is_digit` : `True` if it's a number (0-9).
* `is_vowel` : `True` if it's an English vowel (a, e, i, o, u).
* `is_space` : `True` if it's a whitespace character.

---

## 🛠️ 3. Built-in Functions & Methods

For security, only the following functions and string methods are allowed within the DSL.

### Built-in Functions
* **`chance(probability)`**
  A dice roll function that returns `True` based on a probability (`0.0` to `1.0`). Perfect for random glitch effects!
* **`rmatch(pattern)`**
  Safe regex matching using Google's `re2` engine. Returns `True` if the current character matches the pattern.
* **`leet(char)`**
  Converts a character into LEET speak (e.g., `a`➡`4`, `e`➡`3`).
* **`swap(char)`**
  Swaps uppercase to lowercase and vice versa.
* **`find_char(sub)`**
  Searches the entire text for the specified substring and returns its first index.
* **`range(*args)`**
  Used for loops or checking index ranges. (Hard-capped at 1000 elements to prevent DoS attacks).

### String Methods
Standard Python string methods can be called on string variables (like `char`, `text_before`, `text_after`):
* `.upper()`, `.lower()`, `.swapcase()`, `.title()`
* `.startswith(prefix)`, `.endswith(suffix)`

---

## 🔮 4. Supported Syntax & Operators

Most standard Python expressions (Expressions, not Statements) are supported.

* **Comparison**: `==`, `!=`, `<`, `<=`, `>`, `>=`, `in`
* **Logical**: `and` (or `&&`), `or` (or `||`), `not`
* **Arithmetic**: `+`, `-`, `*`, `/`, `//`, `%`, `**`
* **Ternary Operator**: `A if condition else B`
* **Data Structures**: Lists `[]`, Tuples `()`, Dictionaries `{}`
* **Slicing**: e.g., `text_after[:3]`

---

## 💡 5. Spell Book (Examples)

Here are some powerful DSL snippets you can feed to the bot.

### ① Basic Filter (Capitalize Vowels & Delete Numbers)
Capitalizes vowels, deletes numbers, and leaves everything else alone.
```python
'upper' if is_vowel else ('delete' if is_digit else 'keep')
```

* **Input**: `Hello 123 world!`
* **Output**: `hEllO  wOrld!`

### ② Inline Replacement (Emoji Bomb)

Replaces the letter 'a' with an explosion emoji 💥, and makes everything else lowercase.

```python
'💥' if char.lower() == 'a' else 'lower'
```

### ③ Character Multiplication

Multiplies exclamation marks by 3!

```python
char * 3 if char == '!' else char
```

### ④ Randomized Encryption (Coin Flip Reverse)

If the character is a lowercase letter, there is a 50% chance it flips (A-Z mirroring).

```python
'reverse' if (rmatch('^[a-z]$') and chance(0.5)) else char
```

* **Input**: `test world`
* **Output**: `gves dliwo` *(Changes every run!)*

### ⑤ Advanced Context (First Letter Manipulation)

Converts ONLY the first letter of every space-separated word into LEET speak, and lowercases the rest.

```python
leet(char) if word_idx == 0 else 'lower'
```

### ⑥ Lookahead & Dictionary Mapping

If the *next* character is a `?`, replace the current character with `@`. Otherwise, map it using a custom dictionary.

```python
'@' if next_char == '?' else {'s': '$', 'i': '1'}.get(char.lower(), char)
```

---

## 🛡️ 6. Security & Sandbox Limitations

The pox-bot DSL engine runs inside a strict sandbox to protect the server from malicious inputs.

1. **AST Whitelisting**: Strict `ast.walk` validation blocks unsafe statements. You cannot use loops (`for`, `while`), define functions, or import modules.
2. **ReDoS Protection**: `rmatch` is powered by the `google-re2` engine, making catastrophic backtracking freezes impossible.
3. **Recursion & Load Limits**: Expression nesting is limited to a depth of 50, and `range()` is strictly capped at 1000 elements to prevent memory overloads.
