# Commit Message Guidelines (Conventional Commits 1.0.0)

Please generate commit messages following this strict structure:

## Structure

```
type(scope): description

- List of major/significant changes (if applicable)
```

## Rules
- **Header Format:** Follow the `type(scope): description` pattern on the first line.
- **Allowed Types:** feat, fix, docs, style, refactor, perf, test, chore, ci.
- **Language & Tone:** Write everything in English. Use the imperative, present tense ("add", not "added" or "adds").
- **Case & Punctuation:** Do not capitalize the first letter of the description. Do not add a period (`.`) at the end of lines.
- **Body Section:** 
  - Leave a blank line between the header and the body.
  - If the changes are substantial or complex, provide a concise bulleted list (`- change details`) highlighting only the major, high-level modifications.
  - Skip the body list if the commit is small or self-explanatory.
- **No Emojis:** Do not include any emojis in the header or the body.
