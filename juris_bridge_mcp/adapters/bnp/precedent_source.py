"""The BNP as the Source of Precedents: the JSON backend its web app calls, read anonymously."""

from typing import Any

import httpx

from juris_bridge_mcp.adapters.bnp.precedent_mapper import map_decisions, map_precedent
from juris_bridge_mcp.adapters.http_client import UpstreamClient
from juris_bridge_mcp.adapters.schema_drift import SchemaDrift
from juris_bridge_mcp.domain.errors import ErrorCode, source_changed, source_failure
from juris_bridge_mcp.domain.precedent import (
    COUNT_CAP,
    KINDS,
    SOURCE,
    PrecedentDecisions,
    PrecedentFilters,
    PrecedentPage,
    PrecedentRecord,
)
from juris_bridge_mcp.domain.precedent_bodies import (
    BODIES_WITHOUT_ALIAS,
    PRECEDENT_COURTS,
    body_for_court,
)

# The BNP answers 400 to a search without both arrays, so a search that names no body or kind
# asks for all of them.
_ALL_BODIES = tuple(body_for_court(alias) for alias in PRECEDENT_COURTS) + BODIES_WITHOUT_ALIAS
# The BNP answers 500 to a text search without an ordering.
_ORDERING = "Text"
_FIND_PAGE_SIZE = 10


def _br_date(value: Any) -> str:
    """The BNP reads dates as `DD/MM/YYYY` and ignores ISO ones."""
    return value.strftime("%d/%m/%Y")  # type: ignore[no-any-return]


class BnpPrecedentSource:
    """Implements `PrecedentSource` over the BNP read backend."""

    def __init__(self, client: UpstreamClient, *, base_url: str) -> None:
        """Query `base_url`; the backend needs no key."""
        self._client = client
        self._base_url = base_url.rstrip("/")

    async def search(self, filters: PrecedentFilters, *, page: int, limit: int) -> PrecedentPage:
        """Fetch the page of Precedents that `filters` ask for."""
        body = await self._search(self._filter(filters, page=page, limit=limit))
        try:
            total = body["total"]
            results = body["resultados"]
            if isinstance(total, bool) or not isinstance(total, int):
                raise SchemaDrift("total is not a number")
            if not isinstance(results, list):
                raise SchemaDrift("resultados is not a list")
            precedents = tuple(map_precedent(item) for item in results)
        except (SchemaDrift, KeyError, TypeError) as drift:
            raise source_changed(SOURCE, "BNP", str(drift)) from None
        return PrecedentPage(precedents=precedents, total=total, total_is_capped=total >= COUNT_CAP)

    async def find(self, precedent_id: str) -> PrecedentRecord | None:
        """Look the id up by body, kind and number, since the BNP has no read-by-id endpoint."""
        body_part, kind, number = precedent_id.split("-", 2)
        filtro = {
            "orgaos": [body_part.upper()],
            "tipos": [kind.upper()],
            "nr": int(number) if number.isdigit() else number,
            "cancelados": True,
            "ordenacao": _ORDERING,
            "pagina": 1,
            "tamanhoPagina": _FIND_PAGE_SIZE,
        }
        body = await self._search(filtro)
        try:
            for item in body["resultados"]:
                precedent = map_precedent(item)
                if precedent.id == precedent_id:
                    return PrecedentRecord(precedent)
        except (SchemaDrift, KeyError, TypeError) as drift:
            raise source_changed(SOURCE, "BNP", str(drift)) from None
        return None

    async def decisions(self, precedent_id: str) -> PrecedentDecisions:
        """Fetch the decisions endpoint of a Precedent; a missing one reads as no decisions."""
        response = await self._send("GET", f"/precedentes/{precedent_id}/decisoes")
        if response.status_code == 404:
            return PrecedentDecisions()
        try:
            return map_decisions(self._json(response))
        except SchemaDrift as drift:
            raise source_changed(SOURCE, "BNP", str(drift)) from None

    @staticmethod
    def _filter(filters: PrecedentFilters, *, page: int, limit: int) -> dict[str, Any]:
        filtro: dict[str, Any] = {
            "orgaos": [body_for_court(filters.court)] if filters.court else list(_ALL_BODIES),
            "tipos": [filters.kind] if filters.kind else list(KINDS),
            "cancelados": filters.include_cancelled,
            "ordenacao": _ORDERING,
            "pagina": page,
            "tamanhoPagina": limit,
        }
        if filters.query:
            filtro["buscaGeral"] = filters.query
        if filters.number:
            filtro["nr"] = int(filters.number) if filters.number.isdigit() else filters.number
        if filters.updated_from:
            filtro["atualizacaoDesde"] = _br_date(filters.updated_from)
        if filters.updated_to:
            filtro["atualizacaoAte"] = _br_date(filters.updated_to)
        return filtro

    async def _search(self, filtro: dict[str, Any]) -> dict[str, Any]:
        response = await self._send("POST", "/precedentes", json={"filtro": filtro})
        body = self._json(response)
        if not isinstance(body, dict):
            raise source_changed(SOURCE, "BNP", "the body is not an object")
        return body

    def _json(self, response: httpx.Response) -> Any:
        status = response.status_code
        if status == 403:
            raise source_failure(
                SOURCE,
                ErrorCode.SOURCE_BLOCKED,
                "The BNP refused this server's address.",
                retryable=False,
                hint="The operator must slow down or change the address and report it to the CNJ.",
            )
        if status >= 500:
            raise source_failure(
                SOURCE,
                ErrorCode.SOURCE_UNAVAILABLE,
                f"The BNP is unavailable (HTTP {status}).",
                retryable=True,
            )
        if status != 200:
            raise source_changed(SOURCE, "BNP", f"HTTP {status}")
        try:
            return response.json()
        except ValueError:
            raise source_changed(SOURCE, "BNP", "the body is not JSON") from None

    async def _send(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            return await self._client.request(method, f"{self._base_url}{path}", **kwargs)
        except httpx.HTTPError:
            raise source_failure(
                SOURCE,
                ErrorCode.SOURCE_UNAVAILABLE,
                "The BNP did not answer in time.",
                retryable=True,
            ) from None
