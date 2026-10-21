"""Presents a `PublicationSearchResult` as the Normalized result an MCP client receives."""

from typing import Any

from juris_bridge_mcp.adapters.presentation import iso_utc
from juris_bridge_mcp.application.use_cases.search_publications import PublicationSearchResult
from juris_bridge_mcp.domain.publication import SOURCE, Publication

KIND_CLASSIFICATION_NOTE = (
    "heuristic: `kind` is inferred from the text and the Court's labels, not stated by the "
    "Source; `ambiguous` means no reliable marker was found, so read `document_type` and the "
    "text. Despachos, intimações and editais are dropped."
)


def present_search(result: PublicationSearchResult) -> dict[str, Any]:
    """Return the page of Publications with its totals."""
    presented: dict[str, Any] = {
        "source": SOURCE,
        "retrieved_at": iso_utc(result.retrieved_at),
        "content_kind": "metadata",
        "court": result.court,
        "items": [_item(p) for p in result.publications],
        "total": result.total,
        "total_is_lower_bound": result.total_is_lower_bound,
        "next_cursor": result.next_cursor,
        "not_decisions_dropped": result.not_decisions_dropped,
        "kind_classification": KIND_CLASSIFICATION_NOTE,
    }
    if result.hint is not None:
        presented["hint"] = result.hint
    return presented


def _item(publication: Publication) -> dict[str, Any]:
    return {
        "id": publication.id,
        "source": SOURCE,
        "content_kind": "metadata",
        "citation": {"text": publication.citation_text, "url": publication.url},
        "cnj_number": publication.number.formatted,
        "cnj_number_digits": publication.number.digits,
        "court": publication.court,
        "kind": publication.kind.value,
        "document_type": publication.document_type,
        "published_on": publication.day.isoformat(),
        "excerpt": publication.excerpt,
        "text_length": publication.text_length,
    }
