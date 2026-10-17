FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY juris_bridge_mcp ./juris_bridge_mcp
EXPOSE 8000
CMD ["uv", "run", "--no-dev", "python", "-m", "juris_bridge_mcp.main"]
