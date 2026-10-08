# AGENTS.md

## Project Overview

Multipurposal discord bot made using discord.py
Uses PostgreSQL for Database currently

## Directory Structure

Located at `file-structure.md` (illegularly updated)

## Commands
- Install dependencies: `uv add`
- Run tests: `uv run pytest`
- Lint: `uv run ruff check .`
- Type check: `uv run ruff format --check .`

## Code Style
- File name: snake_case
- Extensions (Cogs): located at `src/extensions`

## Testing
- Framework: pytest
- Coverage goal: over 80%
- Test File: `tests/*.py`

## Internationalization / Localization
- Make sure to be casual, and playful tone when translating (silly tone?)
- Do NOT add the line break before the emoticons

## Git
- Commit message: Follows Conventional Commits
- Branches: Currently only `main`

## Boundaries
- Do not edit/commit `.env*`
- Do not automatically generate `alembic/versions/` migrations
- Must to ask when you have to change production files

## Workflow
- Make sure to follow Conventional Commits for Commit message