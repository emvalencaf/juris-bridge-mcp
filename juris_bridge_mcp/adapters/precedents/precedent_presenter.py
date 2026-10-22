"""Presents the Precedent use-case results as the Normalized result an MCP client receives."""

from datetime import date
from typing import Any

from juris_bridge_mcp.adapters.presentation import iso_utc
from juris_bridge_mcp.application.use_cases.get_precedent import PrecedentResult
from juris_bridge_mcp.application.use_cases.search_precedents import PrecedentSearchResult
from juris_bridge_mcp.domain.precedent import (
    SOURCE,
    LeadingCase,
    Precedent,
    PrecedentDecisions,
    StatusEntry,
    Suspension,
)


def present_search(result: PrecedentSearchResult) -> dict[str, Any]:
    """Return the page of Precedents with its totals."""
    presented: dict[str, Any] = {
        "source": SOURCE,
        "retrieved_at": iso_utc(result.retrieved_at),
        "content_kind": "metadata",
        "total": result.total,
        "total_is_capped": result.total_is_capped,
        "items": [_item(p) for p in result.precedents],
        "next_cursor": result.next_cursor,
    }
    if result.hint is not None:
        presented["hint"] = result.hint
    return presented


def present_precedent(result: PrecedentResult) -> dict[str, Any]:
    """Return one Precedent in full, with its decisions when the Source gave them."""
    precedent = result.precedent
    decisions = result.decisions
    presented = {
        **_item(precedent),
        "retrieved_at": iso_utc(result.retrieved_at),
        "content_kind": "full_text" if decisions and decisions.texts else "metadata",
        "status_history": [_status(entry) for entry in precedent.status_history],
        "leading_cases": [_leading_case(case) for case in precedent.leading_cases],
        "suspensions": [_suspension(s) for s in precedent.suspensions],
        "decisions": _decisions(decisions),
        "warnings": list(result.warnings),
    }
    return presented


def _iso(day: date | None) -> str | None:
    return day.isoformat() if day else None


def _item(precedent: Precedent) -> dict[str, Any]:
    return {
        "id": precedent.id,
        "source": SOURCE,
        "content_kind": "metadata",
        "citation": {"text": f"{precedent.body} {precedent.kind} {precedent.number}", "url": None},
        "court": precedent.court,
        "body": precedent.body,
        "kind": precedent.kind,
        "number": precedent.number,
        "status": precedent.status,
        "question": precedent.question,
        "thesis": precedent.thesis,
        "updated_on": _iso(precedent.updated_on),
        "matched_terms": list(precedent.matched_terms),
    }


def _status(entry: StatusEntry) -> dict[str, Any]:
    return {
        "status": entry.status,
        "recorded_at": iso_utc(entry.recorded_at),
        "admitted_on": _iso(entry.admitted_on),
        "judged_on": _iso(entry.judged_on),
        "published_on": _iso(entry.published_on),
    }


def _leading_case(case: LeadingCase) -> dict[str, Any]:
    return {
        "raw_number": case.raw_number,
        "cnj_number": case.cnj_number.formatted if case.cnj_number else None,
        "cnj_number_digits": case.cnj_number.digits if case.cnj_number else None,
        "case_class": case.case_class,
        "url": case.url,
    }


def _suspension(suspension: Suspension) -> dict[str, Any]:
    return {
        "active": suspension.active,
        "started_on": _iso(suspension.started_on),
        "description": suspension.description,
    }


def _decisions(decisions: PrecedentDecisions | None) -> dict[str, Any] | None:
    if decisions is None:
        return None
    return {
        "reporter": decisions.reporter,
        "tracking_url": decisions.tracking_url,
        "texts": list(decisions.texts),
    }
