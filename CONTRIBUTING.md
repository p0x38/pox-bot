# Contributing to pox-bot

Thank you for your interest in contributing to pox-bot!

This guide explains the basic workflow and conventions used when contributing to the project.

## Development Environment

pox-bot currently targets Python 3.12 and 3.13.

The project uses [uv](https://docs.astral.sh/uv/) for dependency and environment management.

Clone the repository and install the development dependencies with:

```bash
uv sync
```

The default uv configuration installs the project's development dependency groups as configured in `pyproject.toml`.

## Code Style

pox-bot uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting.

Run the linter with:

```bash
uv run ruff check .
```

Check formatting with:

```bash
uv run ruff format --check .
```

To format the code automatically:

```bash
uv run ruff format .
```

New code should use appropriate type annotations and follow the existing project structure and conventions.

## Testing

Tests are written with pytest.

Run the test suite with:

```bash
uv run pytest
```

When fixing a bug or adding a feature, add or update tests when practical.

## Pull Requests

Before opening a pull request:

1. Install the development dependencies with `uv sync`.
2. Run `uv run ruff check .`.
3. Run `uv run ruff format --check .`.
4. Run `uv run pytest`.
5. Review your changes with `git diff`.
6. Make sure your commits have meaningful messages.

Pull requests should briefly explain:

- What was changed
- Why it was changed
- How it was tested
- Any known limitations or breaking changes

Keep pull requests focused when possible. Unrelated changes are usually easier to review when submitted separately.

## Commit Messages

pox-bot follows the [Conventional Commits](https://www.conventionalcommits.org/) format:

```text
<type>[optional scope]: <description>
```

Examples:

```text
feat(markov): add MarkovTokenizer
fix(ai): improve error handling
docs: improve accuracy of docstrings
refactor: strengthen type safety
test(openrouter): add error handling tests
chore(ruff): use explicit rule names for ignores
```

Common types include:

- `feat` — add a new feature
- `fix` — fix a bug
- `docs` — documentation changes
- `refactor` — code restructuring without changing intended behavior
- `test` — add or modify tests
- `perf` — performance improvements
- `build` — build system or dependency changes
- `ci` — CI/CD changes
- `chore` — miscellaneous maintenance

The commit type should describe the main purpose of the commit, not necessarily the number of lines changed.

Prefer descriptions that explain the purpose of the change rather than simply listing files that were modified.

For example:

```text
fix(memory): avoid logging when no objects are collected
```

is generally more useful than:

```text
fix: change memory_manager.py
```

## Issues

When reporting a bug, include enough information to reproduce it whenever possible.

Useful information includes:

- What happened
- What you expected to happen
- Steps to reproduce the problem
- Relevant error messages or logs
- Python and pox-bot versions
- Relevant environment information

For feature requests, describe the problem or use case the feature would solve rather than only proposing a particular implementation.

## Code of Conduct

Please be respectful and constructive when participating in the project.

Contributions, issue reports, and discussions should focus on improving pox-bot and helping other contributors.

## Questions

If you are unsure about a change, feel free to open an issue or discussion before making a large change.
