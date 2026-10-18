"""DataJud as the Source of Cases: one Elasticsearch `_search` per lookup."""

import json
from typing import Any

import httpx

from juris_bridge_mcp.adapters.datajud_case_mapper import SchemaDrift, map_case
from juris_bridge_mcp.adapters.http_client import UpstreamClient
from juris_bridge_mcp.domain.case import CaseRecord
from juris_bridge_mcp.domain.cnj_number import CnjNumber
from juris_bridge_mcp.domain.courts import SOURCE
from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure

_MAX_HITS = 10


def _failure(
    code: ErrorCode, message: str, *, retryable: bool, hint: str | None = None
) -> ToolFailure:
    return ToolFailure(code, message, source=SOURCE, retryable=retryable, hint=hint)


def _changed(detail: str) -> ToolFailure:
    return _failure(
        ErrorCode.SOURCE_CHANGED,
        f"DataJud answered in a shape this server does not understand ({detail}).",
        retryable=False,
        hint="Do not trust partial data; report the problem to the operator.",
    )


class DatajudCaseRepository:
    """Implements `CaseRepository` over the DataJud public API."""

    def __init__(self, client: UpstreamClient, *, base_url: str, api_key: str) -> None:
        """Query `base_url` with the user's own public `api_key`."""
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key

    async def find(self, number: CnjNumber, court: str) -> CaseRecord | None:
        """Look the number up in the Court's index; keep the most recently updated instance."""
        body = await self._search(number, court)
        try:
            hits = self._hits(body)
            if not hits:
                return None
            sources = [hit["_source"] for hit in hits]
            if not all(isinstance(s, dict) for s in sources):
                raise SchemaDrift("a hit has no _source object")
            latest = max(sources, key=lambda s: str(s.get("dataHoraUltimaAtualizacao") or ""))
            case = map_case(latest, number=number, court=court)
        except (SchemaDrift, KeyError, TypeError) as drift:
            raise _changed(str(drift)) from None
        return CaseRecord(case=case, raw=latest, matches=len(sources))

    async def _search(self, number: CnjNumber, court: str) -> Any:
        url = f"{self._base_url}/api_publica_{court}/_search"
        query = {"size": _MAX_HITS, "query": {"match": {"numeroProcesso": number.digits}}}
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
            raise _failure(
                ErrorCode.SOURCE_UNAVAILABLE, "DataJud did not answer in time.", retryable=True
            ) from None
        status = response.status_code
        if status == 401:
            raise _failure(
                ErrorCode.SOURCE_AUTH_FAILED,
                "DataJud rejected the API key.",
                retryable=False,
                hint="The shared public key probably rotated; the operator must update "
                "JURIS_BRIDGE_DATAJUD_API_KEY.",
            )
        if status >= 500:
            raise _failure(
                ErrorCode.SOURCE_UNAVAILABLE,
                f"DataJud is unavailable (HTTP {status}).",
                retryable=True,
            )
        if status != 200:
            raise _changed(f"HTTP {status}")
        try:
            body = response.json()
        except ValueError:
            raise _changed("the body is not JSON") from None
        if isinstance(body, dict) and body.get("timed_out") is True:
            raise _failure(
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
