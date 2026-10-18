"""The Senado open-data API as the Source of Norms: one `legislacao/lista` call per search."""

from datetime import datetime
from typing import Any

import httpx

from juris_bridge_mcp.adapters.http_client import UpstreamClient
from juris_bridge_mcp.adapters.schema_drift import SchemaDrift
from juris_bridge_mcp.domain.errors import ErrorCode, source_changed, source_failure
from juris_bridge_mcp.domain.legislation import (
    NORM_TYPES,
    SOURCE,
    LegislationFilters,
    LegislationPage,
    Norm,
    norm_urn,
)

_SERVICE_VERSION = "3"
_CITATION_URL = "https://normas.leg.br/?urn="


class SenadoLegislationRepository:
    """Implements `LegislationRepository` over the Senado `legislacao` service."""

    def __init__(self, client: UpstreamClient, *, base_url: str) -> None:
        """Query `base_url`, the root of the Senado open-data API."""
        self._client = client
        self._base_url = base_url.rstrip("/")

    async def search(
        self, filters: LegislationFilters, *, limit: int, offset: int = 0
    ) -> LegislationPage:
        """Ask for every match, then slice: the service has no paging of its own."""
        body = await self._get(filters)
        try:
            norms = [self._norm(raw, filters.norm_type) for raw in self._documents(body)]
        except (SchemaDrift, KeyError, TypeError, ValueError) as drift:
            raise source_changed(SOURCE, "The Senado", str(drift) or type(drift).__name__) from None
        end = offset + limit
        return LegislationPage(
            norms=tuple(norms[offset:end]),
            total=len(norms),
            next_offset=end if end < len(norms) else None,
        )

    @staticmethod
    def _documents(body: Any) -> list[Any]:
        documents = body["ListaDocumento"].get("documentos")
        if documents in ("", None, {}):
            return []
        found = documents["documento"]
        if not isinstance(found, list):
            raise SchemaDrift("documentos.documento is not a list")
        return found

    @staticmethod
    def _norm(raw: Any, norm_type: str) -> Norm:
        if not isinstance(raw, dict):
            raise SchemaDrift("a documento is not an object")
        number = int(raw["numero"])
        signed_on = datetime.strptime(raw["dataassinatura"], "%d/%m/%Y").date()
        urn = norm_urn(norm_type, signed_on, number)
        return Norm(
            urn=urn,
            norm_type=norm_type,
            number=number,
            year=signed_on.year,
            signed_on=signed_on,
            name=str(raw["normaNome"]),
            summary=raw.get("ementa") or None,
            nickname=_nickname(raw),
            citation_url=_CITATION_URL + urn,
        )

    async def _get(self, filters: LegislationFilters) -> Any:
        params = {"tipo": NORM_TYPES[filters.norm_type][0], "v": _SERVICE_VERSION}
        if filters.number is not None:
            params["numero"] = str(filters.number)
        if filters.year is not None:
            params["ano"] = str(filters.year)
        try:
            response = await self._client.request(
                "GET",
                f"{self._base_url}/legislacao/lista",
                params=params,
                headers={"Accept": "application/json"},
            )
        except httpx.HTTPError:
            raise source_failure(
                SOURCE,
                ErrorCode.SOURCE_UNAVAILABLE,
                "The Senado did not answer in time.",
                retryable=True,
            ) from None
        status = response.status_code
        if status >= 500:
            raise source_failure(
                SOURCE,
                ErrorCode.SOURCE_UNAVAILABLE,
                f"The Senado is unavailable (HTTP {status}).",
                retryable=True,
            )
        if status != 200:
            raise source_changed(SOURCE, "The Senado", f"HTTP {status}")
        try:
            return response.json()
        except ValueError:
            raise source_changed(SOURCE, "The Senado", "the body is not JSON") from None


def _nickname(raw: dict[str, Any]) -> str | None:
    """Return the popular names in `apelido`, which opens with the norm's own code."""
    parts = [p.strip() for p in str(raw.get("apelido") or "").split(" , ")]
    names = [p for p in parts if p and p != raw.get("norma")]
    return " , ".join(names) or None
