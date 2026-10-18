"""Presents a `LegislationSearchResult` as the Normalized result an MCP client receives."""

from datetime import date
from typing import Any

from juris_bridge_mcp.adapters.presentation import iso_utc
from juris_bridge_mcp.application.use_cases.legislation.get_legislation import NormResult
from juris_bridge_mcp.application.use_cases.legislation.norm_text_slice import TextSlice
from juris_bridge_mcp.application.use_cases.legislation.search_legislation import (
    LegislationSearchResult,
)
from juris_bridge_mcp.domain.legislation import SOURCE, Norm, Publication, Relation


def present_norm(result: NormResult) -> dict[str, Any]:
    """Return the Norm with its publications, bounded relations and `relations_total`."""
    presented: dict[str, Any] = {
        "source": SOURCE,
        "retrieved_at": iso_utc(result.retrieved_at),
        "content_kind": "metadata" if result.text is None else "full_text",
        **_norm(result.norm),
        "publications": [_publication(p) for p in result.publications],
        "relations": [_relation(r) for r in result.relations],
        "relations_total": result.relations_total,
        "warnings": list(result.warnings),
    }
    if result.raw is not None:
        presented["raw"] = result.raw
    if result.text is not None:
        presented.update(_text(result.text))
    return presented


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


def _text(piece: TextSlice) -> dict[str, Any]:
    presented: dict[str, Any] = {
        "text": piece.text,
        "truncated": piece.truncated,
        "next_text_cursor": piece.next_cursor,
        "text_source": piece.source,
        "text_url": piece.url,
    }
    if piece.article is not None:
        presented["article"] = {"label": piece.article.label, "flags": list(piece.article.flags)}
    return presented


def _publication(publication: Publication) -> dict[str, Any]:
    return {
        "kind": publication.kind,
        "edition": publication.edition,
        "published_on": _day(publication.published_on),
        "page": publication.page,
        "column": publication.column,
    }


def _relation(relation: Relation) -> dict[str, Any]:
    return {"kind": relation.kind, "name": relation.name, "signed_on": _day(relation.signed_on)}


def _day(day: date | None) -> str | None:
    return day.isoformat() if day else None
