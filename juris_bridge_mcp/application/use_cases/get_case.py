"""Use case: fetch one Case by CNJ number."""

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any

from juris_bridge_mcp.domain.case import Case
from juris_bridge_mcp.domain.cnj_number import CnjNumber, derive_court
from juris_bridge_mcp.domain.courts import SOURCE, resolve_court
from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure, not_found
from juris_bridge_mcp.domain.raw_payload import bounded_raw
from juris_bridge_mcp.ports.case_repository import CaseRepository

DEFAULT_EVENTS_LIMIT = 20
MAX_EVENTS_LIMIT = 100


@dataclass(frozen=True)
class CaseResult:
    """A Case ready to present: events cut to the limit, with what the cut left out.

    `raw` is the unstable upstream payload, present only when asked for and small enough.
    """

    case: Case
    events_total: int
    retrieved_at: datetime
    warnings: tuple[str, ...] = ()
    raw: dict[str, Any] | None = field(default=None)


async def get_case(
    repository: CaseRepository,
    *,
    number: str,
    court: str | None = None,
    events_limit: int = DEFAULT_EVENTS_LIMIT,
    include_raw: bool = False,
) -> CaseResult:
    """Return the Case for `number`; the Court comes from `court` or from the number itself.

    Events are the most recent `events_limit`, oldest first.
    """
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
        raise not_found(
            SOURCE,
            f"No case {cnj.formatted} in {alias.upper()}.",
            "Check the number, or pass court if the case is held by another Court.",
        )
    case, warnings = record.case, []
    if record.matches > 1:
        warnings.append(
            f"{record.matches} records exist for this number (one per instance); "
            f"showing the most recently updated, instance {case.instance}."
        )
    raw = None
    if include_raw:
        raw, omitted = bounded_raw(record.raw)
        if omitted:
            warnings.append(omitted)
    events = sorted(case.events, key=lambda e: e.occurred_at or datetime.min.replace(tzinfo=UTC))
    return CaseResult(
        case=replace(case, events=tuple(events[-events_limit:])),
        events_total=len(events),
        retrieved_at=record.retrieved_at,
        warnings=tuple(warnings),
        raw=raw,
    )
