"""The DJEN as the Source of Publications: one `comunicacao` search per call."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any

import httpx

from juris_bridge_mcp.adapters.djen.publication_mapper import map_publication
from juris_bridge_mcp.adapters.http_client import UpstreamClient
from juris_bridge_mcp.adapters.schema_drift import SchemaDrift
from juris_bridge_mcp.domain.cnj_number import CnjNumber
from juris_bridge_mcp.domain.errors import (
    ErrorCode,
    rate_limited,
    source_changed,
    source_failure,
)
from juris_bridge_mcp.domain.publication import COUNT_CAP, SOURCE, PublicationPage

# The DJEN documents a page size of 5 or 100 and nothing else. The largest is asked for, since
# despachos and notices are dropped afterwards and a small page could leave nothing to show.
_PAGE_SIZE = 100
# The DJEN says to wait a minute after a 429.
RATE_LIMIT_WAIT_SECONDS = 60
# The client must not retry a 429 within seconds: that is what the DJEN blocks.
RETRIED_STATUSES = frozenset({503})


class _DepthCeiling(Exception):  # noqa: N818 - control flow inside this module
    """The DJEN answered HTTP 500 past its undocumented depth ceiling."""

    def __init__(self, requests: int) -> None:
        super().__init__()
        self.requests = requests


class DjenPublicationRepository:
    """Implements `PublicationRepository` over the DJEN public read API."""

    def __init__(
        self,
        client: UpstreamClient,
        *,
        base_url: str,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        """Query `base_url`; the API needs no key. `sleep` waits out a 429."""
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._sleep = sleep or asyncio.sleep

    async def search(
        self,
        court: str,
        query: str,
        date_from: date,
        date_to: date,
        *,
        page: int = 1,
        organ_id: int | None = None,
        number: CnjNumber | None = None,
    ) -> PublicationPage:
        """Fetch page `page` of the Court's Publications in the window, `query` as it is."""
        params: dict[str, Any] = {
            "siglaTribunal": court.upper(),
            "dataDisponibilizacaoInicio": date_from.isoformat(),
            "dataDisponibilizacaoFim": date_to.isoformat(),
            "itensPorPagina": _PAGE_SIZE,
            "pagina": page,
        }
        if query:
            params["texto"] = query
        if number is not None:
            params["numeroProcesso"] = number.digits
        if organ_id is not None:
            params["orgaoId"] = organ_id
        try:
            body, requests = await self._get(params, ceiling_possible=page > 1)
        except _DepthCeiling as ceiling:
            return PublicationPage(
                publications=(), total=COUNT_CAP, truncated=True, requests=ceiling.requests
            )
        try:
            items, count = body["items"], body["count"]
            if not isinstance(items, list):
                raise SchemaDrift("items is not a list")
            if isinstance(count, bool) or not isinstance(count, int):
                raise SchemaDrift("count is not a number")
            publications = tuple(map_publication(item, court=court) for item in items)
        except (SchemaDrift, KeyError, TypeError) as drift:
            raise source_changed(SOURCE, "DJEN", str(drift)) from None
        return PublicationPage(
            publications=publications,
            total=count,
            more=count > page * _PAGE_SIZE,
            requests=requests,
        )

    async def _get(self, params: dict[str, Any], *, ceiling_possible: bool) -> tuple[Any, int]:
        """Return the body and how many requests it took."""
        response = await self._send(params)
        requests = 1
        if response.status_code == 429:
            await self._sleep(RATE_LIMIT_WAIT_SECONDS)
            response = await self._send(params)
            requests = 2
        status = response.status_code
        if status == 500 and ceiling_possible:
            raise _DepthCeiling(requests)
        if status == 429:
            raise rate_limited(
                SOURCE,
                "The DJEN is rate limiting this server.",
                retry_after_seconds=RATE_LIMIT_WAIT_SECONDS,
            )
        if status == 403:
            raise source_failure(
                SOURCE,
                ErrorCode.SOURCE_BLOCKED,
                "The DJEN refused this server's address.",
                retryable=False,
                hint="The DJEN blocks what it takes for abuse; the operator must slow down "
                "or change the address and report it to the Source.",
            )
        if status >= 500:
            raise source_failure(
                SOURCE,
                ErrorCode.SOURCE_UNAVAILABLE,
                f"The DJEN is unavailable (HTTP {status}).",
                retryable=True,
            )
        if status != 200:
            raise source_changed(SOURCE, "DJEN", f"HTTP {status}")
        try:
            body = response.json()
        except ValueError:
            raise source_changed(SOURCE, "DJEN", "the body is not JSON") from None
        if not isinstance(body, dict):
            raise source_changed(SOURCE, "DJEN", "the body is not an object")
        return body, requests

    async def _send(self, params: dict[str, Any]) -> httpx.Response:
        try:
            return await self._client.request(
                "GET", f"{self._base_url}/api/v1/comunicacao", params=params
            )
        except httpx.HTTPError:
            raise source_failure(
                SOURCE,
                ErrorCode.SOURCE_UNAVAILABLE,
                "The DJEN did not answer in time.",
                retryable=True,
            ) from None
