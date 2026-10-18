"""Composition root: builds the adapters and mounts one FastMCP sub-server per concept."""

from fastmcp import FastMCP
from starlette.middleware import Middleware
from starlette.types import ASGIApp

from juris_bridge_mcp.adapters.bearer_auth import BearerAuthMiddleware
from juris_bridge_mcp.adapters.coverage_mcp_tools import build_coverage_server
from juris_bridge_mcp.adapters.static_coverage_catalog import StaticCoverageCatalog


def build_server() -> FastMCP:
    """Build the root FastMCP server with every concept mounted (no namespace)."""
    app = FastMCP("juris-bridge-mcp")
    app.mount(build_coverage_server(StaticCoverageCatalog()))
    return app


def build_http_app(keys: tuple[str, ...]) -> ASGIApp:
    """Build the stateless, JSON-response ASGI app guarded by Bearer auth."""
    return build_server().http_app(
        path="/mcp",
        stateless_http=True,
        json_response=True,
        middleware=[Middleware(BearerAuthMiddleware, keys=keys)],
    )
