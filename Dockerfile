FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY juris_bridge_mcp ./juris_bridge_mcp
EXPOSE 8000
# The venv is on PATH, so nothing is resolved or written at start (a Lambda filesystem is read-only).
CMD ["python", "-m", "juris_bridge_mcp.main"]
