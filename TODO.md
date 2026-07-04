# Rewrite `src/cogs/*.py` into `src/extensions/*.py`

## Goals
- Port legacy `src/cogs/*.py` logic into modern `src/extensions/*.py` extensions.
- Use current `PoxBot` and `self.bot.database.*` access patterns.
- Optimize where possible using built-in libraries, `numpy`, and existing dependencies.
- Keep the extension structure consistent with existing `src/extensions/*` files.

## Priority files
1. `utility.py`
2. `info.py`
3. `logger.py`
4. `llm_chat.py`
5. `metrics.py`
6. smaller ones: `channel.py`, `converters.py`, `fun.py`, `role.py`, etc.
7. larger ones: `chatbot.py`, `generator.py`, `image.py`, `tts.py`

## Rewrite plan

### 1. Audit and compare
- Enumerate all `src/cogs/*.py` files.
- Compare with existing `src/extensions/*.py` to avoid duplicate behavior.
- Identify which legacy commands are already available in extensions.

### 2. Use extension-style structure
- `from src.core.bot import PoxBot`
- `class XxxCog(commands.Cog):`
- `async def setup(bot: PoxBot): await bot.add_cog(XxxCog(bot))`
- Keep `app_commands`, `discord.ui`, and async listeners.

### 3. Database access style
- Replace `self.bot.settings_db` with `self.bot.database.settings`.
- Replace legacy `self.bot.database.<...>` with proper `self.bot.database.<db>.get_locale(...)` usage.
- Use guards: `hasattr(self.bot, "database") and self.bot.database and self.bot.database.settings`.

### 4. Built-in Python optimizations
- Use `pathlib.Path` instead of `os.path` where possible.
- Use `collections.defaultdict`, `Counter`, `deque` when useful.
- Use `functools.cache` / `lru_cache` for repeated computations.
- Use `itertools` for batching, chaining, grouping.
- Use `contextlib.asynccontextmanager` for async resource contexts.

### 5. Use `numpy` for random/stats math
- Use `np.random.default_rng()` instead of `random`.
- Use `np.choice`, `np.integers`, `np.bincount`, `np.mean` for dice and sampling.
- Use numpy vectorization in numeric-heavy code (`generator.py`, `tts.py`, signal/audio processing).

### 6. Use existing dependencies where appropriate
- Prefer `orjson` for JSON speed in heavy data flows.
- Keep `aiofiles` for async file I/O.
- Use `aiohttp` or `httpx` for async HTTP if needed.
- Reuse installed libs: `psutil`, `pillow`, `moviepy`, `tldextract`, `urlextract`, etc.

### 7. Concurrency improvements
- Use `asyncio.gather` or `asyncio.TaskGroup` for parallel async operations.
- Keep event loop friendly, avoid blocking sync work in bot commands.
- Use `tasks.loop` in dedicated extension cogs only.

### 8. Add tracing / metrics where useful
- Use `self.bot.metrics.span_async(...)` in async flows.
- Use `self.bot.metrics.increment_counter` and `record_histogram` in command handlers.
- Preserve existing `self.bot.metrics` guards.

### 9. Clean style and typing
- Add explicit typing where beneficial.
- Keep `py312` style and `ruff` line length rules.
- Prefer early returns and small helper methods.

### 10. Validation
- Run `uv run ruff check src/extensions`
- Run targeted pytest tests for rewritten features.
- Smoke-test Discord commands if possible.

## Optional enhancement ideas
- Add new commands that use `numpy` math or statistics.
- Add metrics spans for high-cost operations.
- Add `info` / `utility` commands that leverage `self.bot.database` state.
- Convert `src/cogs/utility.py` patterns into new extension equivalents.

## File-level rewrite TODOs

### Highest value files
- `src/cogs/utility.py`
  - Already rewritten in `src/extensions/utility.py`.
  - Verify locale access uses `self.bot.database.settings`.
  - Add numpy-backed commands and keep `listapps` as-is.
- `src/cogs/info.py`
  - Port rich UI view logic into `src/extensions/info.py`.
  - Simplify platform/psutil logic and use `self.bot.database.settings`.
- `src/cogs/logger.py`
  - Move into `src/extensions/logger.py` and align with existing logging setup.

### Medium value files
- `src/cogs/llm_chat.py`
  - Compare against existing `src/extensions/llm_chat.py`.
  - Reuse new extension style and add `self.bot.metrics.span_async(... )` if tracing is enabled.
- `src/cogs/metrics.py`
  - If there is not a direct extension equivalent, create one under `src/extensions/metrics.py`.
  - Keep OTLP metrics, add better async gauge updates, and use current `self.bot.metrics` conventions.
- `src/cogs/minecraft.py`
  - Rewrite into `src/extensions/minecraft.py` with command and interaction logic.
- `src/cogs/converters.py`
  - Convert to extension commands and use built-in conversion helpers.
- `src/cogs/role.py`, `channel.py`, `settings.py`
  - Port command groups into extensions with command checks and `app_commands` groups.

### Lower priority / large rewrites
- `src/cogs/chatbot.py`
  - Large feature set; port gradually and optimize streaming, prompt handling, and rate limiting.
- `src/cogs/generator.py`
  - Use numpy vector math and move into `src/extensions/generator.py`.
- `src/cogs/image.py`
  - Port image generation commands and use `Pillow` / `moviepy` where already installed.
- `src/cogs/tts.py`
  - Rewrite to fit extension style and abstract voice provider logic.
- `src/cogs/user.py`, `giveaway.py`, `economy.py`
  - Longer-term conversion; these are best done after smaller utility/command cogs.

## Optimization-specific tasks
- Use `numpy` for the following patterns:
  - random command results (`8ball`, `yes_or_no`, `coinflip`, `roll`)
  - math and signal generation (`generator.py`)
- Use `orjson` for any `json.loads`/`dumps` in high-frequency workflows.
- Replace `random` with `np.random.default_rng()` in any new extensions.
- Replace `os.path` + `open` with `pathlib.Path` + `aiofiles` for cleaner async file operations.
- Use `asyncio.gather` and `TaskGroup` for parallel database or HTTP calls.
- Use `self.bot.metrics` guard style consistently in rewritten extensions.

## Additional notes
- Keep the repo’s existing dependency set in mind: additional installs should be justified.
- Use `uv add` only when a new library is clearly beneficial, not just because it is available.
- Focus on porting behavior first, then optimize command internals second.

## Next steps
1. Choose one file from `High value files` and port it completely into `src/extensions/`.
2. Run `uv run ruff check src/extensions` after each ported file.
3. Add a targeted pytest file or test case for the new extension feature.
4. Validate locale/database access via `self.bot.database.settings` in the new extension.
5. Commit each port with a descriptive Conventional Commit message.
6. Repeat for the next file, using the same checklist.
