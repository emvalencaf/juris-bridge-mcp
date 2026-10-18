from contextlib import asynccontextmanager

import httpx
import pytest
from fastmcp import Client

from juris_bridge_mcp.bootstrap import build_http_app, build_server
from juris_bridge_mcp.config.server import ServerSettings


@pytest.fixture
def settings(monkeypatch) -> ServerSettings:
    monkeypatch.setenv("JURIS_BRIDGE_SERVER_API_KEYS", "key-one,key-two")
    return ServerSettings(_env_file=None)


@pytest.fixture
async def mcp_client():
    """In-memory MCP client over the real root server."""
    async with Client(build_server()) as client:
        yield client


@pytest.fixture
def asgi_client(settings):
    """Factory for an HTTP client over the real ASGI app, no network.

    Use as `async with asgi_client() as client`: the app lifespan must open and
    close inside the test's own task.
    """

    @asynccontextmanager
    async def open_client():
        app = build_http_app(settings.keys())
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                yield client

    return open_client
