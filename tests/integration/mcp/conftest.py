import json
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest
from fastmcp import Client

from juris_bridge_mcp.config.datajud import DatajudSettings
from juris_bridge_mcp.config.http import HttpSettings
from juris_bridge_mcp.config.senado import SenadoSettings
from juris_bridge_mcp.config.server import ServerSettings
from juris_bridge_mcp.infrastructure.bootstrap import build_http_app, build_server

DATAJUD_FIXTURES = Path(__file__).parents[2] / "contract/providers/datajud/fixtures"
SENADO_FIXTURES = Path(__file__).parents[2] / "contract/providers/senado/fixtures"


def datajud_fixture(name: str) -> dict:
    return json.loads((DATAJUD_FIXTURES / name).read_text())


class FakeDatajud:
    """Scripted DataJud: replace `body`/`status` to change the answer; `requests` records calls."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.status = 200
        self.body: dict = datajud_fixture("trf1_hit.json")

    @staticmethod
    def fixture(name: str) -> dict:
        return datajud_fixture(name)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(self.status, json=self.body)


class FakeSenado:
    """Scripted Senado: replace `body`/`status` to change the answer; `requests` records calls."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.status = 200
        self.body: dict = self.fixture("lei_14133_2021.json")

    @staticmethod
    def fixture(name: str) -> dict:
        return json.loads((SENADO_FIXTURES / name).read_text())

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(self.status, json=self.body)


@pytest.fixture
def senado() -> FakeSenado:
    return FakeSenado()


@pytest.fixture
def datajud() -> FakeDatajud:
    return FakeDatajud()


@pytest.fixture
def server_args(datajud, senado) -> dict:
    """Settings and transport the root server is built with: no network, fake Sources."""
    senado_host = httpx.URL(SenadoSettings().base_url).host

    def route(request: httpx.Request) -> httpx.Response:
        return senado(request) if request.url.host == senado_host else datajud(request)

    return {
        "datajud": DatajudSettings(api_key="test-key"),
        "http": HttpSettings(),
        "senado": SenadoSettings(),
        "transport": httpx.MockTransport(route),
    }


@pytest.fixture
def settings(monkeypatch) -> ServerSettings:
    monkeypatch.setenv("JURIS_BRIDGE_SERVER_API_KEYS", "key-one,key-two")
    return ServerSettings(_env_file=None)


@pytest.fixture
async def mcp_client(server_args):
    """In-memory MCP client over the real root server."""
    async with Client(build_server(**server_args)) as client:
        yield client


@pytest.fixture
def asgi_client(settings, server_args):
    """Factory for an HTTP client over the real ASGI app, no network.

    Use as `async with asgi_client() as client`: the app lifespan must open and
    close inside the test's own task.
    """

    @asynccontextmanager
    async def open_client():
        app = build_http_app(settings.keys(), **server_args)
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                yield client

    return open_client
