"""Presents a `CaseResult` as the Normalized result an MCP client receives."""

from datetime import UTC, date, datetime
from typing import Any

from juris_bridge_mcp.application.use_cases.get_case import CaseResult
from juris_bridge_mcp.domain.case import CaseEvent, CodedTerm, EventComplement
from juris_bridge_mcp.domain.courts import SOURCE


def present_case(result: CaseResult) -> dict[str, Any]:
    """Return the Case with its `source`, Citation (no URL), `retrieved_at` and Content kind."""
    case = result.case
    presented: dict[str, Any] = {
        "source": SOURCE,
        "citation": {
            "text": f"DataJud · {case.court.upper()} · {case.number.formatted}",
            "url": None,
        },
        "retrieved_at": _iso(result.retrieved_at),
        "content_kind": "metadata",
        "number": case.number.formatted,
        "number_digits": case.number.digits,
        "court": case.court,
        "instance": case.instance,
        "filed_on": _day(case.filed_on),
        "class": _term(case.case_class),
        "subjects": [_term(t) for t in case.subjects],
        "judging_body": _term(case.judging_body),
        "secrecy_level": case.secrecy_level,
        "source_system": _term(case.source_system),
        "last_updated_at": _iso(case.last_updated_at),
        "events": [_event(e) for e in case.events],
        "events_total": result.events_total,
        "warnings": list(result.warnings),
    }
    if result.raw is not None:
        presented["raw"] = result.raw
    return presented


def _iso(moment: datetime | None) -> str | None:
    if moment is None:
        return None
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _day(day: date | None) -> str | None:
    return day.isoformat() if day else None


def _term(term: CodedTerm | None) -> dict[str, Any] | None:
    return None if term is None else {"code": term.code, "name": term.name}


def _event(event: CaseEvent) -> dict[str, Any]:
    return {
        "code": event.term.code,
        "name": event.term.name,
        "occurred_at": _iso(event.occurred_at),
        "judging_body": _term(event.judging_body),
        "complements": [_complement(c) for c in event.complements],
    }


def _complement(complement: EventComplement) -> dict[str, Any]:
    return {
        "code": complement.term.code,
        "name": complement.term.name,
        "kind": complement.kind,
        "value": complement.value,
    }
