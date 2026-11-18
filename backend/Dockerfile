# syntax=docker/dockerfile:1
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.9 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    TIKTOKEN_CACHE_DIR=/opt/tiktoken \
    PATH="/app/backend/.venv/bin:$PATH"

WORKDIR /app/backend

# Dependencies first, so code changes do not invalidate this layer.
COPY pyproject.toml uv.lock .python-version ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY data/snapshot ./data/snapshot
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev \
    # The chunker's tokenizer data is downloaded on first use; bake it into the image.
    && python -c "import tiktoken; tiktoken.get_encoding('cl100k_base')"

RUN useradd --create-home app && mkdir -p data/runtime && chown -R app data/runtime
USER app

EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=90s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"

# On first start the search index is built from the committed snapshot (~10 s, needs the key).
CMD ["uvicorn", "compileit_chat.interface.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
