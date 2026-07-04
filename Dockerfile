FROM ghcr.io/astral-sh/uv:latest AS uv

FROM python:3.12-slim

WORKDIR /app

COPY --from=uv /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY . .

RUN uv sync --frozen

CMD ["uv", "run", "poxbot"]