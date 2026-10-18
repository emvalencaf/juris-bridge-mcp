"""Composition root: builds the root server and mounts one sub-server per module."""

from fastmcp import FastMCP
from starlette.middleware import Middleware
from starlette.types import ASGIApp

from juris_bridge_mcp.modules.coverage.infrastructure import container as coverage
from juris_bridge_mcp.shared.auth import BearerAuthMiddleware


def build_server() -> FastMCP:
    """Build the root FastMCP server with every module mounted (no namespace)."""
    app = FastMCP("juris-bridge-mcp")
    app.mount(coverage.build_server())
    return app


def build_http_app(keys: tuple[str, ...]) -> ASGIApp:
    """Build the stateless, JSON-response ASGI app guarded by Bearer auth."""
    return build_server().http_app(
        path="/mcp",
        stateless_http=True,
        json_response=True,
        middleware=[Middleware(BearerAuthMiddleware, keys=keys)],
    )
