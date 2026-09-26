FROM ghcr.io/astral-sh/uv:0.10.11 AS uv
FROM python:3.12-slim
COPY --from=uv /uv /usr/local/bin/uv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
ENV TIKTOKEN_CACHE_DIR=/app/tokenizer-cache
RUN .venv/bin/python -c "import tiktoken; tiktoken.get_encoding('cl100k_base')"
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
RUN useradd --create-home pilot && chown -R pilot:pilot /app
USER pilot
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
