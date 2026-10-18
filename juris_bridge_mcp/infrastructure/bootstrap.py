"""Composition root: builds the adapters and mounts one FastMCP sub-server per concept."""

from collections.abc import Mapping
from typing import Any

from fastmcp import FastMCP
from starlette.middleware import Middleware
from starlette.types import ASGIApp

from juris_bridge_mcp.adapters.bearer_auth import BearerAuthMiddleware
from juris_bridge_mcp.adapters.coverage_mcp_tools import build_coverage_server
from juris_bridge_mcp.adapters.static_coverage_catalog import StaticCoverageCatalog
from juris_bridge_mcp.adapters.wide_event_middleware import WideEventMiddleware


def build_server() -> FastMCP:
    """Build the root FastMCP server with every concept mounted (no namespace)."""
    app = FastMCP("juris-bridge-mcp")
    app.mount(build_coverage_server(StaticCoverageCatalog()))
    return app


def build_http_app(keys: tuple[str, ...], environment: Mapping[str, Any] | None = None) -> ASGIApp:
    """Build the stateless, JSON-response ASGI app: wide event outermost, then Bearer auth."""
    return build_server().http_app(
        path="/mcp",
        stateless_http=True,
        json_response=True,
        middleware=[
            Middleware(WideEventMiddleware, environment=environment),
            Middleware(BearerAuthMiddleware, keys=keys),
        ],
    )
