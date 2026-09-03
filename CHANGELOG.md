# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Bug Fixes
- Add names of each `uv lock --check` by @p0x38

### CI
- Fix install method by @p0x38

### Documentation
- Add conventional commits note by @p0x38

### Features
- Update OpenRouter adapter by @p0x38

### Testing
- Update OpenRouter tests for Pygent adapter by @p0x38

## [1.1.0] - 2026-09-03

### Bug Fixes
- Improved error handling method for _on_tree_error by @p0x38
- Cliff.toml render syntax were invalid by @p0x38
- Activity.py will be not emitting error message when ConnectionClosed, ClientConnectionError or HTTPException was raised by @p0x38
- Memory_manager.py will not log when collected objects was 0 by @p0x38
- Removed TTSEngineType from exceptions __init__.py because of it was unnessecary import syntax by @p0x38
- Improve error handling by @p0x38
- Improve error handling by @p0x38
- Configure type checking paths by @p0x38
- Fix data type on database by @p0x38
- Fix markov model scope not working by @p0x38
- Fix chatbot_runtime.py by @p0x38
- Fix diagnostics stuff to work by @p0x38
- Register smart trigger extension by @p0x38
- Use existing LLM service export by @p0x38
- Prioritize explicit smart triggers by @p0x38
- Apply smart trigger cooldown to AI by @p0x38
- Preserve TF-IDF document ordering by @p0x38
- Add Discord mention sanitizer by @p0x38
- Serialize saves and strip Discord mentions by @p0x38
- Fix test file by @p0x38
- Honor configured LLM provider by @p0x38
- Fix provider settings not reflecting by @p0x38
- Remove try clause by @p0x38

### Build
- Move some non-MIT compatible packages to optional dependencies by @p0x38
- Fix dependencies for ci errors by @p0x38
- Add uv lockfile by @p0x38
- Bump astral-sh/setup-uv from 6 to 7 by @dependabot[bot]
- Bump github/codeql-action from 3 to 4 by @dependabot[bot]
- Bump actions/checkout from 4 to 7 by @dependabot[bot]
- Bump actions/setup-python from 5 to 7 by @dependabot[bot]
- Remove conflicting openrouter dependency by @p0x38
- Fix dependency metadata options by @p0x38

### CI
- Separate workflows by @p0x38
- Rename test to Test by @p0x38
- Update CI workflow files by @p0x38
- Re-combine into ci.yml by @p0x38
- Update ci.yml and codeql.yml by @p0x38

### Documentation
- Generated CHANGELOG.md via git-cliff by @p0x38
- Add contributing guide by @p0x38
- Remove unnecessary ignore comments by @p0x38
- Add ignore comments and fixes by @p0x38
- Track configurable LLM provider by @p0x38

### Features
- Many stuff by @p0x38
- Many changes i can't describe sorry by @p0x38
- Added TUI support by using textual by @p0x38
- Added dashboard property for TUI with textual package by @p0x38
- Added embed_exceptions for embed error displaying method in future use by @p0x38
- Added user_flags for Discord API's User flag feature by @p0x38
- Added Japanese translation for displaying of exception handling by @p0x38
- Added more status texts by @p0x38
- Added many features by @p0x38
- Added Chatbot Config by @p0x38
- Improve extension manager by @p0x38
- Add MarkovGenerator by @p0x38
- Add MarkovModel by @p0x38
- Add MarkovGenerator by @p0x38
- Add MarkovStorage by @p0x38
- Add MarkovTokenizer by @p0x38
- Add markov-related settings by @p0x38
- Add markov-based chat system by @p0x38
- Add chat feature i guess by @p0x38
- Add lightweight dialogue memory by @p0x38
- Integrate dialogue retrieval by @p0x38
- Improve markov-based chat system by @p0x38
- Add runtime reload control by @p0x38
- Add Markov learning diagnostics by @p0x38
- Add backend abstraction by @p0x38
- Add Markovify generation backend by @p0x38
- Route generation through backend by @p0x38
- Add smart trigger evaluator by @p0x38
- Add smart conversational triggers by @p0x38
- Add lightweight TF-IDF index by @p0x38
- Replace fuzzy dialogue retrieval with TF-IDF by @p0x38
- Integrate Pygent agent by @p0x38
- Add Pygent Ollama support by @p0x38
- Add configurable LLM provider by @p0x38

### Miscellaneous Chores
- Some unusual or smth else change by @p0x38
- Biggest changes ever I did by @p0x38
- Remove unnessary log data by @p0x38
- Mass by @p0x38
- Mass 2 by @p0x38
- Updated .gitignore by @p0x38
- Updated Dockerfile by @p0x38
- Updated dependencies by @p0x38
- Updated VSCode settings; unrelated to the codebase by @p0x38
- Refactor extension names by @p0x38
- Update ruff.toml by @p0x38
- Add SECURITY.md by @p0x38
- Remove unnecessary stuffs by @p0x38
- Update todo by @p0x38
- Settings change by @p0x38
- Add discord utility package by @p0x38
- Update .gitignore by @p0x38
- Update settings.json in local reason by @p0x38
- Update uv lockfile by @p0x38
- Bump to 1.1.0 by @p0x38

### Other
- ) by @p0x38
- 3 by @p0x38
- 3 by @p0x38
- I18n support by @p0x38

### Refactor
- Renamed llm_chat.py to chatbot.py for future use by @p0x38
- Refactor error message by @p0x38
- Simplify runtime reload response by @p0x38
- Keep native backend independent by @p0x38
- Expose backend generator by @p0x38
- Make smart trigger evaluation conservative by @p0x38
- Keep mention sanitization in tokenizer by @p0x38
- Route OpenRouter through Pygent by @p0x38
- Refactor pyproject.toml by @p0x38

### Revert
- Remove unused discord utility package by @p0x38

### Testing
- Add test of LLM error handling by @p0x38
- Add test of OpenRouter function by @p0x38
- Update entire codebase by @p0x38
- Cover Markov runtime cache reload by @p0x38
- Cover Markov config round-trip by @p0x38
- Cover Markovify backend by @p0x38
- Refine smart trigger rules by @p0x38
- Add smart trigger coverage by @p0x38
- Cover TF-IDF similarity by @p0x38
- Cover TF-IDF dialogue retrieval by @p0x38
- Cover Discord mention sanitization by @p0x38
- Cover configured LLM provider by @p0x38
- Focus provider configuration coverage by @p0x38

### New Contributors
* @p0x38 made their first contribution
* @dependabot[bot] made their first contribution
* @crowdin-bot made their first contribution

[unreleased]: https://github.com/p0x38/pox-bot/compare/v1.1.0...HEAD

<!-- generated by git-cliff -->
