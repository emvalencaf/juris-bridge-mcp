"""Composition root: builds the adapters and mounts one FastMCP sub-server per concept."""

from collections.abc import Mapping
from typing import Any

import httpx
from fastmcp import FastMCP
from starlette.middleware import Middleware
from starlette.types import ASGIApp

from juris_bridge_mcp.adapters.bearer_auth import BearerAuthMiddleware
from juris_bridge_mcp.adapters.cases.cached_case_repository import CachedCaseRepository
from juris_bridge_mcp.adapters.cases.cases_mcp_tools import build_cases_server
from juris_bridge_mcp.adapters.coverage_mcp_tools import build_coverage_server
from juris_bridge_mcp.adapters.datajud.case_repository import DatajudCaseRepository
from juris_bridge_mcp.adapters.http_client import UpstreamClient, build_http_client
from juris_bridge_mcp.adapters.in_memory_ttl_cache import InMemoryTtlCache
from juris_bridge_mcp.adapters.legislation.legislation_mcp_tools import build_legislation_server
from juris_bridge_mcp.adapters.planalto.norm_text_source import PlanaltoNormTextSource
from juris_bridge_mcp.adapters.rate_limiter import RateLimiter
from juris_bridge_mcp.adapters.senado.legislation_repository import SenadoLegislationRepository
from juris_bridge_mcp.adapters.static_coverage_catalog import StaticCoverageCatalog
from juris_bridge_mcp.adapters.wide_event_middleware import WideEventMiddleware
from juris_bridge_mcp.config.datajud import DatajudSettings
from juris_bridge_mcp.config.http import HttpSettings
from juris_bridge_mcp.config.planalto import PlanaltoSettings
from juris_bridge_mcp.config.senado import SenadoSettings
from juris_bridge_mcp.domain.courts import SOURCE as DATAJUD
from juris_bridge_mcp.domain.legislation import SOURCE as SENADO
from juris_bridge_mcp.domain.legislation_text import TEXT_SOURCE as PLANALTO


def build_server(
    *,
    datajud: DatajudSettings,
    http: HttpSettings,
    senado: SenadoSettings,
    planalto: PlanaltoSettings,
    transport: httpx.AsyncBaseTransport | None = None,
) -> FastMCP:
    """Build the root FastMCP server with every concept mounted (no namespace).

    `transport` replaces the network for tests; production leaves it `None`.
    """
    upstream = UpstreamClient(
        build_http_client(timeout_seconds=datajud.timeout_seconds, transport=transport),
        source=DATAJUD,
        limiter=RateLimiter(
            DATAJUD,
            max_requests=datajud.requests_per_minute,
            window_seconds=60,
            max_wait_seconds=http.max_wait_seconds,
        ),
        max_retries=http.max_retries,
        max_wait_seconds=http.max_wait_seconds,
    )
    senado_upstream = UpstreamClient(
        build_http_client(timeout_seconds=senado.timeout_seconds, transport=transport),
        source=SENADO,
        limiter=RateLimiter(
            SENADO,
            max_requests=senado.requests_per_minute,
            window_seconds=60,
            max_wait_seconds=http.max_wait_seconds,
        ),
        max_retries=http.max_retries,
        max_wait_seconds=http.max_wait_seconds,
    )
    planalto_upstream = UpstreamClient(
        build_http_client(timeout_seconds=planalto.timeout_seconds, transport=transport),
        source=PLANALTO,
        limiter=RateLimiter(
            PLANALTO,
            max_requests=planalto.requests_per_minute,
            window_seconds=60,
            max_wait_seconds=http.max_wait_seconds,
        ),
        max_retries=http.max_retries,
        max_wait_seconds=http.max_wait_seconds,
    )
    cases = CachedCaseRepository(
        DatajudCaseRepository(
            upstream, base_url=datajud.base_url, api_key=datajud.api_key.get_secret_value()
        ),
        InMemoryTtlCache(),
        ttl_seconds=datajud.cache_ttl_seconds,
    )
    app = FastMCP("juris-bridge-mcp")
    app.mount(build_coverage_server(StaticCoverageCatalog()))
    app.mount(build_cases_server(cases))
    app.mount(
        build_legislation_server(
            SenadoLegislationRepository(senado_upstream, base_url=senado.base_url),
            PlanaltoNormTextSource(planalto_upstream, base_url=planalto.base_url),
        )
    )
    return app


def build_http_app(
    keys: tuple[str, ...],
    environment: Mapping[str, Any] | None = None,
    *,
    datajud: DatajudSettings,
    http: HttpSettings,
    senado: SenadoSettings,
    planalto: PlanaltoSettings,
    transport: httpx.AsyncBaseTransport | None = None,
) -> ASGIApp:
    """Build the stateless, JSON-response ASGI app: wide event outermost, then Bearer auth."""
    server = build_server(
        datajud=datajud, http=http, senado=senado, planalto=planalto, transport=transport
    )
    return server.http_app(
        path="/mcp",
        stateless_http=True,
        json_response=True,
        middleware=[
            Middleware(WideEventMiddleware, environment=environment),
            Middleware(BearerAuthMiddleware, keys=keys),
        ],
    )
