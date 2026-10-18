"""Use case: search the Cases of a Court by class, judging body, subject and filing date."""

from dataclasses import dataclass
from datetime import date, datetime

from juris_bridge_mcp.domain.case import Case
from juris_bridge_mcp.domain.case_search import CaseFilters
from juris_bridge_mcp.domain.courts import resolve_court
from juris_bridge_mcp.domain.cursor import Cursor
from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure
from juris_bridge_mcp.ports.case_repository import CaseRepository

DEFAULT_LIMIT = 10
MAX_LIMIT = 50


@dataclass(frozen=True)
class SearchResult:
    """A page of Cases ready to present, with the cursor to the next one."""

    court: str
    cases: tuple[Case, ...]
    total: int
    total_is_lower_bound: bool
    next_cursor: str | None
    retrieved_at: datetime
    hint: str | None = None


def _invalid(message: str, hint: str | None = None) -> ToolFailure:
    return ToolFailure(ErrorCode.INVALID_ARGUMENT, message, source=None, retryable=False, hint=hint)


async def search_cases(
    repository: CaseRepository,
    *,
    court: str | None = None,
    case_class: int | None = None,
    judging_body: int | None = None,
    subject: int | None = None,
    filed_from: date | None = None,
    filed_to: date | None = None,
    limit: int = DEFAULT_LIMIT,
    cursor: str | None = None,
) -> SearchResult:
    """Return one page of the Court's Cases matching every filter given.

    With a `cursor`, the Court comes from it (and `court`, if also given, must agree);
    the filters must be the ones the cursor was issued for.
    """
    if not 1 <= limit <= MAX_LIMIT:
        raise _invalid(f"limit must be between 1 and {MAX_LIMIT}.")
    if filed_from and filed_to and filed_from > filed_to:
        raise _invalid("filed_from is after filed_to.")
    filters = CaseFilters(case_class, judging_body, subject, filed_from, filed_to)
    after = None
    if cursor is not None:
        decoded = Cursor.decode(cursor)
        alias = resolve_court(court) if court else decoded.court
        if alias != decoded.court or decoded.filters_key != filters.key():
            raise _invalid(
                "The cursor was issued for a different court or different filters.",
                hint="Repeat the same court and filters, or start again without a cursor.",
            )
        after = decoded.position
    elif court is None:
        raise _invalid("court is required.", hint="Pass an alias such as tjsp, trf1 or stj.")
    else:
        alias = resolve_court(court)
    page = await repository.search(alias, filters, limit=limit, after=after)
    next_cursor = (
        Cursor(alias, page.next_position, filters.key()).encode() if page.next_position else None
    )
    hint = None
    if page.total_is_lower_bound:
        hint = (
            f"At least {page.total} cases match and the Source counts no further; "
            "narrow with filed_from/filed_to, case_class, judging_body or subject."
        )
    return SearchResult(
        court=alias,
        cases=page.cases,
        total=page.total,
        total_is_lower_bound=page.total_is_lower_bound,
        next_cursor=next_cursor,
        retrieved_at=page.retrieved_at,
        hint=hint,
    )
