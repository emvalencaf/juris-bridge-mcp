# Reference deployment image: the portable image plus the Lambda Web Adapter (ADR 0003).
# Build from the repo root: docker build -f deploy/aws/Dockerfile .
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1 /lambda-adapter /opt/extensions/lambda-adapter
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    JURIS_BRIDGE_SERVER_PORT=8000 \
    AWS_LWA_PORT=8000 \
    AWS_LWA_INVOKE_MODE=buffered \
    AWS_LWA_READINESS_CHECK_PATH=/mcp \
    AWS_LWA_READINESS_CHECK_MIN_UNHEALTHY_STATUS=500
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY juris_bridge_mcp ./juris_bridge_mcp
CMD ["python", "-m", "juris_bridge_mcp.main"]
