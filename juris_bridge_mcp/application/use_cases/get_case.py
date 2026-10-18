"""Use case: fetch one Case by CNJ number as a Normalized result."""

import json
from datetime import UTC, date, datetime
from typing import Any

from juris_bridge_mcp.domain.case import Case, CaseEvent, CodedTerm, EventComplement
from juris_bridge_mcp.domain.cnj_number import CnjNumber, derive_court
from juris_bridge_mcp.domain.courts import SOURCE, resolve_court
from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure
from juris_bridge_mcp.ports.case_repository import CaseRepository

DEFAULT_EVENTS_LIMIT = 20
MAX_EVENTS_LIMIT = 100
MAX_RAW_BYTES = 256 * 1024


async def get_case(
    repository: CaseRepository,
    *,
    number: str,
    court: str | None = None,
    events_limit: int = DEFAULT_EVENTS_LIMIT,
    include_raw: bool = False,
) -> dict[str, Any]:
    """Return the Case for `number`; the Court comes from `court` or from the number itself."""
    if not 1 <= events_limit <= MAX_EVENTS_LIMIT:
        raise ToolFailure(
            ErrorCode.INVALID_ARGUMENT,
            f"events_limit must be between 1 and {MAX_EVENTS_LIMIT}.",
            source=None,
            retryable=False,
        )
    cnj = CnjNumber.parse(number)
    alias = resolve_court(court) if court else derive_court(cnj)
    record = await repository.find(cnj, alias)
    if record is None:
        raise ToolFailure(
            ErrorCode.NOT_FOUND,
            f"No case {cnj.formatted} in {alias.upper()}.",
            source=SOURCE,
            retryable=False,
            hint="Check the number, or pass court if the case is held by another Court.",
        )
    case, warnings = record.case, []
    if record.matches > 1:
        warnings.append(
            f"{record.matches} records exist for this number (one per instance); "
            f"showing the most recently updated, instance {case.instance}."
        )
    result = _normalize(case, events_limit, record.retrieved_at)
    if include_raw:
        raw = {"unstable": True, "payload": record.raw}
        if len(json.dumps(raw, ensure_ascii=False)) > MAX_RAW_BYTES:
            warnings.append(f"raw payload omitted: larger than {MAX_RAW_BYTES // 1024} KiB.")
        else:
            result["raw"] = raw
    result["warnings"] = warnings
    return result


def _normalize(case: Case, events_limit: int, retrieved_at: datetime) -> dict[str, Any]:
    events = sorted(case.events, key=lambda e: e.occurred_at or datetime.min.replace(tzinfo=UTC))
    return {
        "source": SOURCE,
        "citation": {
            "text": f"DataJud · {case.court.upper()} · {case.number.formatted}",
            "url": None,
        },
        "retrieved_at": _iso(retrieved_at),
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
        "events": [_event(e) for e in events[-events_limit:]],
        "events_total": len(events),
    }


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
        "code": event.code,
        "name": event.name,
        "occurred_at": _iso(event.occurred_at),
        "judging_body": _term(event.judging_body),
        "complements": [_complement(c) for c in event.complements],
    }


def _complement(complement: EventComplement) -> dict[str, Any]:
    return {
        "code": complement.code,
        "name": complement.name,
        "kind": complement.kind,
        "value": complement.value,
    }
