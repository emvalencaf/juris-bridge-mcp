"""DataJud as the Source of Cases: one Elasticsearch `_search` per lookup."""

import json
from datetime import UTC, datetime
from typing import Any

import httpx

from juris_bridge_mcp.adapters.datajud.case_mapper import map_case
from juris_bridge_mcp.adapters.http_client import UpstreamClient
from juris_bridge_mcp.adapters.schema_drift import SchemaDrift
from juris_bridge_mcp.domain.case import Case, CaseRecord
from juris_bridge_mcp.domain.case_search import CaseFilters, CasePage
from juris_bridge_mcp.domain.cnj_number import CnjNumber
from juris_bridge_mcp.domain.courts import SOURCE
from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure, source_changed, source_failure

_MAX_HITS = 10
_NEVER = datetime.min.replace(tzinfo=UTC)
# `@timestamp` alone ties; `id.keyword` makes the order total, so paging never skips or repeats.
_SORT = [{"@timestamp": {"order": "asc"}}, {"id.keyword": {"order": "asc"}}]


class DatajudCaseRepository:
    """Implements `CaseRepository` over the DataJud public API."""

    def __init__(self, client: UpstreamClient, *, base_url: str, api_key: str) -> None:
        """Query `base_url` with the user's own public `api_key`."""
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key

    async def find(self, number: CnjNumber, court: str) -> CaseRecord | None:
        """Look the number up in the Court's index; keep the most recently updated instance."""
        query = {"size": _MAX_HITS, "query": {"match": {"numeroProcesso": number.digits}}}
        body = await self._search(court, query)
        try:
            hits = self._hits(body)
            if not hits:
                return None
            sources = [hit["_source"] for hit in hits]
            if not all(isinstance(s, dict) for s in sources):
                raise SchemaDrift("a hit has no _source object")
            cases = [map_case(s, number=number, court=court) for s in sources]
            newest = max(range(len(cases)), key=lambda i: cases[i].last_updated_at or _NEVER)
        except (SchemaDrift, KeyError, TypeError) as drift:
            raise source_changed(SOURCE, "DataJud", str(drift)) from None
        return CaseRecord(case=cases[newest], raw=sources[newest], matches=len(sources))

    async def search(
        self,
        court: str,
        filters: CaseFilters,
        *,
        limit: int,
        after: tuple[int | str, int | str] | None = None,
    ) -> CasePage:
        """Run the filters on the Court's index, one extra hit telling if another page follows."""
        query: dict[str, Any] = {
            "size": limit + 1,
            "query": {"bool": {"filter": self._clauses(filters)}},
            "sort": _SORT,
        }
        if after is not None:
            query["search_after"] = list(after)
        body = await self._search(court, query)
        try:
            hits = self._hits(body)
            total = body["hits"]["total"]
            value, relation = total["value"], total["relation"]
            if isinstance(value, bool) or not isinstance(value, int):
                raise SchemaDrift("hits.total.value is not a number")
            more = len(hits) > limit
            page = hits[:limit]
            cases = tuple(self._case(hit, court) for hit in page)
            position = tuple(page[-1]["sort"]) if more else None
            if position is not None and (
                len(position) != 2 or not all(isinstance(p, int | str) for p in position)
            ):
                raise SchemaDrift("a hit has no usable sort position")
        except (SchemaDrift, KeyError, TypeError) as drift:
            raise source_changed(SOURCE, "DataJud", str(drift)) from None
        return CasePage(
            cases=cases,
            total=value,
            total_is_lower_bound=relation == "gte",
            next_position=position,
        )

    @staticmethod
    def _clauses(filters: CaseFilters) -> list[dict[str, Any]]:
        clauses: list[dict[str, Any]] = []
        for field, value in (
            ("classe.codigo", filters.case_class),
            ("orgaoJulgador.codigo", filters.judging_body),
            ("assuntos.codigo", filters.subject),
        ):
            if value is not None:
                clauses.append({"term": {field: value}})
        # Compact civil timestamps, compared as DataJud stores them. An explicit `format`
        # makes the index answer nothing, and no time zone shifts the day (checked live).
        bounds: dict[str, str] = {}
        if filters.filed_from:
            bounds["gte"] = f"{filters.filed_from:%Y%m%d}000000"
        if filters.filed_to:
            bounds["lte"] = f"{filters.filed_to:%Y%m%d}235959"
        if bounds:
            clauses.append({"range": {"dataAjuizamento": bounds}})
        return clauses or [{"match_all": {}}]

    @staticmethod
    def _case(hit: Any, court: str) -> Case:
        source = hit["_source"]
        if not isinstance(source, dict):
            raise SchemaDrift("a hit has no _source object")
        digits = source.get("numeroProcesso")
        try:
            number = CnjNumber.parse(str(digits))
        except ToolFailure:
            raise SchemaDrift("a hit has no valid numeroProcesso") from None
        return map_case(source, number=number, court=court)

    async def _search(self, court: str, query: dict[str, Any]) -> Any:
        url = f"{self._base_url}/api_publica_{court}/_search"
        try:
            response = await self._client.request(
                "POST",
                url,
                content=json.dumps(query),
                headers={
                    "Authorization": f"APIKey {self._api_key}",
                    "Content-Type": "application/json",
                },
            )
        except httpx.HTTPError:
            raise source_failure(
                SOURCE,
                ErrorCode.SOURCE_UNAVAILABLE,
                "DataJud did not answer in time.",
                retryable=True,
            ) from None
        status = response.status_code
        if status == 401:
            raise source_failure(
                SOURCE,
                ErrorCode.SOURCE_AUTH_FAILED,
                "DataJud rejected the API key.",
                retryable=False,
                hint="The shared public key probably rotated; the operator must update "
                "JURIS_BRIDGE_DATAJUD_API_KEY.",
            )
        if status >= 500:
            raise source_failure(
                SOURCE,
                ErrorCode.SOURCE_UNAVAILABLE,
                f"DataJud is unavailable (HTTP {status}).",
                retryable=True,
            )
        if status != 200:
            raise source_changed(SOURCE, "DataJud", f"HTTP {status}")
        try:
            body = response.json()
        except ValueError:
            raise source_changed(SOURCE, "DataJud", "the body is not JSON") from None
        if isinstance(body, dict) and body.get("timed_out") is True:
            raise source_failure(
                SOURCE,
                ErrorCode.SOURCE_UNAVAILABLE,
                "DataJud timed out running the search.",
                retryable=True,
            )
        return body

    @staticmethod
    def _hits(body: Any) -> list[Any]:
        hits = body["hits"]["hits"]
        if not isinstance(hits, list):
            raise SchemaDrift("hits.hits is not a list")
        return hits
