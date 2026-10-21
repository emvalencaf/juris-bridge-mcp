"""The DJEN as the Source of Publications: one `comunicacao` search per call."""

from datetime import date
from typing import Any

import httpx

from juris_bridge_mcp.adapters.djen.publication_mapper import map_publication
from juris_bridge_mcp.adapters.http_client import UpstreamClient
from juris_bridge_mcp.adapters.schema_drift import SchemaDrift
from juris_bridge_mcp.domain.errors import (
    ErrorCode,
    rate_limited,
    source_changed,
    source_failure,
)
from juris_bridge_mcp.domain.publication import SOURCE, PublicationPage

# The DJEN documents a page size of 5 or 100 and nothing else. The largest is asked for, since
# despachos and notices are dropped afterwards and a small page could leave nothing to show.
_PAGE_SIZE = 100
# The DJEN says to wait a minute after a 429.
RATE_LIMIT_WAIT_SECONDS = 60
# The client must not retry a 429 within seconds: that is what the DJEN blocks.
RETRIED_STATUSES = frozenset({503})


class DjenPublicationRepository:
    """Implements `PublicationRepository` over the DJEN public read API."""

    def __init__(self, client: UpstreamClient, *, base_url: str) -> None:
        """Query `base_url`; the API needs no key."""
        self._client = client
        self._base_url = base_url.rstrip("/")

    async def search(
        self, court: str, query: str, date_from: date, date_to: date, *, page: int = 1
    ) -> PublicationPage:
        """Fetch page `page` of the Court's Publications in the window, `query` as it is."""
        body = await self._get(
            {
                "siglaTribunal": court.upper(),
                "texto": query,
                "dataDisponibilizacaoInicio": date_from.isoformat(),
                "dataDisponibilizacaoFim": date_to.isoformat(),
                "itensPorPagina": _PAGE_SIZE,
                "pagina": page,
            }
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
        )

    async def _get(self, params: dict[str, Any]) -> Any:
        try:
            response = await self._client.request(
                "GET", f"{self._base_url}/api/v1/comunicacao", params=params
            )
        except httpx.HTTPError:
            raise source_failure(
                SOURCE,
                ErrorCode.SOURCE_UNAVAILABLE,
                "The DJEN did not answer in time.",
                retryable=True,
            ) from None
        status = response.status_code
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
        return body
