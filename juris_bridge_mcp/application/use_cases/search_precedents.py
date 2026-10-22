"""Use case: search Precedents by text, Court, kind, number and update date."""

from dataclasses import dataclass
from datetime import date, datetime

from juris_bridge_mcp.domain.cursor import Cursor
from juris_bridge_mcp.domain.errors import invalid_argument
from juris_bridge_mcp.domain.precedent import (
    COUNT_CAP,
    SOURCE,
    Precedent,
    PrecedentFilters,
    resolve_kind,
)
from juris_bridge_mcp.domain.precedent_bodies import resolve_precedent_court
from juris_bridge_mcp.ports.precedent_source import PrecedentSource

DEFAULT_LIMIT = 10
MAX_LIMIT = 50


@dataclass(frozen=True)
class PrecedentSearchResult:
    """A page of Precedents ready to present, with the cursor to the next one."""

    precedents: tuple[Precedent, ...]
    total: int
    total_is_capped: bool
    body_counts: tuple[tuple[str, int], ...]
    next_cursor: str | None
    retrieved_at: datetime
    hint: str | None = None


async def search_precedents(
    source: PrecedentSource,
    *,
    query: str | None = None,
    court: str | None = None,
    kind: str | None = None,
    number: str | None = None,
    updated_from: date | None = None,
    updated_to: date | None = None,
    include_cancelled: bool = False,
    limit: int = DEFAULT_LIMIT,
    cursor: str | None = None,
) -> PrecedentSearchResult:
    """Return one page of the Precedents matching every filter given.

    The filters and `limit` must be the ones a `cursor` was issued for. The Source shows no
    more than `COUNT_CAP` results, so a cursor past that is refused.
    """
    if not 1 <= limit <= MAX_LIMIT:
        raise invalid_argument(f"limit must be between 1 and {MAX_LIMIT}.")
    if updated_from and updated_to and updated_from > updated_to:
        raise invalid_argument("updated_from is after updated_to.")
    filters = PrecedentFilters(
        query=query.strip() or None if query else None,
        court=resolve_precedent_court(court) if court else None,
        kind=resolve_kind(kind) if kind else None,
        number=number.strip() or None if number else None,
        updated_from=updated_from,
        updated_to=updated_to,
        include_cancelled=include_cancelled,
    )
    key = f"{filters.key()}|{limit}"
    page_number = 1
    if cursor is not None:
        decoded = Cursor.decode(cursor, scopes=(SOURCE,))
        if decoded.filters_key != key:
            raise invalid_argument(
                "The cursor was issued for different filters or a different limit.",
                hint="Repeat the same filters and limit, or start again without a cursor.",
            )
        page_number = decoded.offset()
        if page_number < 1 or page_number * limit > COUNT_CAP:
            raise invalid_argument(
                f"The Source shows no more than {COUNT_CAP} results for a search.",
                hint="Narrow the search with query, court, kind or updated_from/updated_to.",
            )
    page = await source.search(filters, page=page_number, limit=limit)
    reached = page_number * limit
    more = reached < min(page.total, COUNT_CAP)
    next_cursor = Cursor(SOURCE, (page_number + 1,), key).encode() if more else None
    hint = None
    if page.total_is_capped:
        hint = (
            f"At least {page.total} precedents match and the Source counts no further; "
            "narrow with court, kind or updated_from/updated_to."
        )
    return PrecedentSearchResult(
        precedents=page.precedents,
        total=page.total,
        total_is_capped=page.total_is_capped,
        body_counts=page.body_counts,
        next_cursor=next_cursor,
        retrieved_at=page.retrieved_at,
        hint=hint,
    )
