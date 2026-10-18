"""Use case: locate a federal Norm by type, number and year."""

from dataclasses import dataclass
from datetime import datetime

from juris_bridge_mcp.domain.cursor import Cursor
from juris_bridge_mcp.domain.errors import invalid_argument
from juris_bridge_mcp.domain.legislation import (
    SOURCE,
    LegislationFilters,
    Norm,
    resolve_norm_type,
)
from juris_bridge_mcp.ports.legislation_repository import LegislationRepository

DEFAULT_LIMIT = 10
MAX_LIMIT = 50


@dataclass(frozen=True)
class LegislationSearchResult:
    """A page of Norms ready to present, with the cursor to the next one."""

    norms: tuple[Norm, ...]
    total: int
    next_cursor: str | None
    retrieved_at: datetime


async def search_legislation(
    repository: LegislationRepository,
    *,
    norm_type: str,
    number: int | None = None,
    year: int | None = None,
    limit: int = DEFAULT_LIMIT,
    cursor: str | None = None,
) -> LegislationSearchResult:
    """Return one page of the Norms of a type, narrowed by number and year.

    A `cursor` must come with the same type, number and year it was issued for.
    """
    if not 1 <= limit <= MAX_LIMIT:
        raise invalid_argument(f"limit must be between 1 and {MAX_LIMIT}.")
    filters = LegislationFilters(resolve_norm_type(norm_type), number, year)
    if number is None and year is None:
        raise invalid_argument(
            "Pass number, year or both.", hint="For example number=14133, year=2021."
        )
    if (number is not None and number < 1) or (year is not None and year < 1):
        raise invalid_argument("number and year must be positive.")
    offset = 0
    if cursor is not None:
        decoded = Cursor.decode(cursor, scopes=(SOURCE,))
        if decoded.filters_key != filters.key():
            raise invalid_argument(
                "The cursor was issued for a different search.",
                hint="Repeat the same type, number and year, or start again without a cursor.",
            )
        position = decoded.position[0]
        if isinstance(position, str) or position < 0:
            raise invalid_argument("The cursor is not valid.")
        offset = position
    page = await repository.search(filters, limit=limit, offset=offset)
    next_cursor = (
        Cursor(SOURCE, (page.next_offset, 0), filters.key()).encode()
        if page.next_offset is not None
        else None
    )
    return LegislationSearchResult(page.norms, page.total, next_cursor, page.retrieved_at)
