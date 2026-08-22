FROM astral-sh/uv:python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
	UV_LINK_MODE=copy

WORKDIR /app

# Install locked dependencies before copying application code so this layer is cacheable.
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
	uv sync --frozen --no-install-project --no-dev

COPY src/ ./src/
RUN --mount=type=cache,target=/root/.cache/uv \
	uv sync --frozen --no-dev


FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get update \
	&& apt-get install --no-install-recommends -y ffmpeg \
	&& rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/.venv /app/.venv
COPY src/ /app/src/
COPY data/ /app/data/
COPY config.yml commands.json ./

ENV PATH="/app/.venv/bin:$PATH"

CMD ["poxbot", "run"]