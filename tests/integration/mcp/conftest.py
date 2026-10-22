import json
from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest
from fastmcp import Client

from juris_bridge_mcp.config.bnp import BnpSettings
from juris_bridge_mcp.config.datajud import DatajudSettings
from juris_bridge_mcp.config.djen import DjenSettings
from juris_bridge_mcp.config.http import HttpSettings
from juris_bridge_mcp.config.legin import LeginSettings
from juris_bridge_mcp.config.planalto import PlanaltoSettings
from juris_bridge_mcp.config.senado import SenadoSettings
from juris_bridge_mcp.config.server import ServerSettings
from juris_bridge_mcp.infrastructure.bootstrap import build_http_app, build_server

DATAJUD_FIXTURES = Path(__file__).parents[2] / "contract/providers/datajud/fixtures"
SENADO_FIXTURES = Path(__file__).parents[2] / "contract/providers/senado/fixtures"
PLANALTO_FIXTURES = Path(__file__).parents[2] / "contract/providers/planalto/fixtures"
LEGIN_FIXTURES = Path(__file__).parents[2] / "contract/providers/legin/fixtures"
DJEN_FIXTURES = Path(__file__).parents[2] / "contract/providers/djen/fixtures"
BNP_FIXTURES = Path(__file__).parents[2] / "contract/providers/bnp/fixtures"


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


class FakeDjen:
    """Scripted DJEN: replace `body`/`status` to change the answer; `requests` records calls."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.status = 200
        self.body: dict = self.fixture("tjsp_decisions.json")
        # When set, answers each request instead of `body`.
        self.responder: Callable[[httpx.Request], dict] | None = None

    @staticmethod
    def fixture(name: str) -> dict:
        return json.loads((DJEN_FIXTURES / name).read_text())

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        body = self.responder(request) if self.responder else self.body
        return httpx.Response(self.status, json=body)


class FakeBnp:
    """Scripted BNP: replace `search_body`/`decisions_body` or the statuses to change the answers.

    `requests` records every call; `filters` is the `filtro` of the last search.
    """

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.search_status = 200
        self.search_body: dict | str = self.fixture("stf_rg_1002.json")
        self.decisions_status = 200
        self.decisions_body: dict | str = self.fixture("decisoes_stf_rg_1002.json")
        # When set, answers each search with the `filtro` it received instead of `search_body`.
        self.responder: Callable[[dict], dict] | None = None

    @staticmethod
    def fixture(name: str) -> dict:
        return json.loads((BNP_FIXTURES / name).read_text())

    @property
    def filters(self) -> dict:
        searches = [r for r in self.requests if r.method == "POST"]
        return json.loads(searches[-1].content)["filtro"]

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.method == "POST":
            body = self.responder(self.filters) if self.responder else self.search_body
            return self._answer(self.search_status, body)
        return self._answer(self.decisions_status, self.decisions_body)

    @staticmethod
    def _answer(status: int, body: dict | str) -> httpx.Response:
        if isinstance(body, str):
            return httpx.Response(status, content=body.encode())
        return httpx.Response(status, json=body)


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


class FakePlanalto:
    """Scripted Planalto: `pages` maps a path to its HTML bytes; `requests` records calls.

    A path not in `pages` answers 404; set `status` to answer every request with it instead.
    """

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.status: int | None = None
        self.pages: dict[str, bytes] = {}

    @staticmethod
    def fixture(name: str) -> bytes:
        return (PLANALTO_FIXTURES / name).read_bytes()

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.status is not None:
            return httpx.Response(self.status, content=b"refused")
        body = self.pages.get(request.url.path.removeprefix("/ccivil_03/"))
        if body is None:
            return httpx.Response(404, content=b"not found")
        return httpx.Response(200, content=body, headers={"Content-Type": "text/html"})


class FakeLegin:
    """Scripted LexML and Câmara Legin: `pages` maps a URL path to its HTML bytes.

    A path not in `pages` answers the LexML "urn não encontrada" page for `/urn/...` and 404
    for any other; `requests` records calls.
    """

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.pages: dict[str, bytes] = {}

    @staticmethod
    def fixture(name: str) -> bytes:
        return (LEGIN_FIXTURES / name).read_bytes()

    def serve_cpc(self) -> None:
        """Script the whole chain for Lei 13.105/2015 (the Código de Processo Civil)."""
        folder = "/legin/fed/lei/2015/lei-13105-16-marco-2015-780273-"
        self.pages["/urn/urn:lex:br:federal:lei:2015-03-16;13105"] = self.fixture(
            "lexml_lei_13105_2015.htm"
        )
        self.pages[folder + "norma-pl.html"] = self.fixture("camara_sheet_lei_13105_2015.htm")
        self.pages[folder + "normaatualizada-pl.html"] = self.fixture(
            "camara_text_lei_13105_2015.htm"
        )

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        body = self.pages.get(request.url.path)
        if body is None and request.url.path.startswith("/urn/"):
            body = self.fixture("lexml_urn_not_found.htm")
        if body is None:
            return httpx.Response(404, content=b"not found")
        return httpx.Response(200, content=body, headers={"Content-Type": "text/html"})


@pytest.fixture
def legin() -> FakeLegin:
    return FakeLegin()


@pytest.fixture
def planalto() -> FakePlanalto:
    return FakePlanalto()


@pytest.fixture
def senado() -> FakeSenado:
    return FakeSenado()


@pytest.fixture
def bnp() -> FakeBnp:
    return FakeBnp()


@pytest.fixture
def djen() -> FakeDjen:
    return FakeDjen()


@pytest.fixture
def datajud() -> FakeDatajud:
    return FakeDatajud()


@pytest.fixture
def server_args(datajud, djen, bnp, senado, planalto, legin) -> dict:
    """Settings and transport the root server is built with: no network, fake Sources."""
    senado_host = httpx.URL(SenadoSettings().base_url).host
    planalto_host = httpx.URL(PlanaltoSettings().base_url).host
    djen_host = httpx.URL(DjenSettings().base_url).host
    bnp_host = httpx.URL(BnpSettings().base_url).host
    legin_hosts = {httpx.URL(LeginSettings().lexml_base_url).host, "www2.camara.leg.br"}

    def route(request: httpx.Request) -> httpx.Response:
        if request.url.host == senado_host:
            return senado(request)
        if request.url.host == djen_host:
            return djen(request)
        if request.url.host == bnp_host:
            return bnp(request)
        if request.url.host in legin_hosts:
            return legin(request)
        return planalto(request) if request.url.host == planalto_host else datajud(request)

    return {
        "datajud": DatajudSettings(api_key="test-key"),
        "djen": DjenSettings(),
        "bnp": BnpSettings(),
        "http": HttpSettings(),
        "senado": SenadoSettings(),
        "planalto": PlanaltoSettings(),
        "legin": LeginSettings(),
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
