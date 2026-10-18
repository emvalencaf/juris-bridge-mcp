"""Presents a `LegislationSearchResult` as the Normalized result an MCP client receives."""

from typing import Any

from juris_bridge_mcp.adapters.presentation import iso_utc
from juris_bridge_mcp.application.use_cases.search_legislation import LegislationSearchResult
from juris_bridge_mcp.domain.legislation import SOURCE, Norm


def present_search(result: LegislationSearchResult) -> dict[str, Any]:
    """Return the page of Norms with its `total` and `next_cursor`."""
    return {
        "source": SOURCE,
        "retrieved_at": iso_utc(result.retrieved_at),
        "content_kind": "metadata",
        "items": [_norm(n) for n in result.norms],
        "total": result.total,
        "next_cursor": result.next_cursor,
    }


def _norm(norm: Norm) -> dict[str, Any]:
    return {
        "citation": {"text": f"Senado · {norm.name}", "url": norm.citation_url},
        "urn": norm.urn,
        "type": norm.norm_type,
        "number": norm.number,
        "year": norm.year,
        "signed_on": norm.signed_on.isoformat(),
        "name": norm.name,
        "summary": norm.summary,
        "nickname": norm.nickname,
    }
