"""Use case: search the Publications of a Court released in a window of days."""

from dataclasses import dataclass
from datetime import date, datetime

from juris_bridge_mcp.domain.cursor import Cursor
from juris_bridge_mcp.domain.errors import invalid_argument
from juris_bridge_mcp.domain.publication import COUNT_CAP, Publication
from juris_bridge_mcp.domain.publication_courts import resolve_djen_court
from juris_bridge_mcp.domain.publication_kind import DECISION_KINDS, PublicationKind
from juris_bridge_mcp.ports.publication_repository import PublicationRepository

DEFAULT_LIMIT = 10
MAX_LIMIT = 25
MAX_WINDOW_DAYS = 31
# The DJEN answers a page of 100 and gives up past its undocumented depth ceiling, which is
# also where its count stops (`COUNT_CAP`).
MAX_DJEN_PAGE = COUNT_CAP // 100
# Pages read for one call, so a filter that keeps little cannot fan out without end.
MAX_PAGES_PER_CALL = 3
# The DJEN answers a trimmed query shorter than this with a misleading HTTP 500.
MIN_QUERY_LENGTH = 5


@dataclass(frozen=True)
class PublicationSearchResult:
    """A page of Publications ready to present."""

    court: str
    publications: tuple[Publication, ...]
    total: int
    total_is_lower_bound: bool
    next_cursor: str | None
    retrieved_at: datetime
    not_decisions_dropped: int = 0
    hint: str | None = None


async def search_publications(
    repository: PublicationRepository,
    *,
    court: str,
    date_from: date,
    date_to: date,
    query: str,
    kind: str | None = None,
    limit: int = DEFAULT_LIMIT,
    cursor: str | None = None,
) -> PublicationSearchResult:
    """Return a page of the Court's decisions in the window whose text matches `query`.

    The query goes to the Source as it is, trimmed; nothing is called when an argument is
    invalid. Despachos, intimações and editais are dropped from what the Source answers (the
    `total` still counts them), and `kind`, when given, keeps only that kind; without it every
    decision stays, `ambiguous` included. Up to `MAX_PAGES_PER_CALL` pages of the Source are
    read to fill `limit`; `next_cursor` resumes after the last Publication returned and must
    come back with the same Court, window, query and kind.
    """
    wanted = _parse_kind(kind)
    if not 1 <= limit <= MAX_LIMIT:
        raise invalid_argument(f"limit must be between 1 and {MAX_LIMIT}.")
    if date_from > date_to:
        raise invalid_argument("date_from is after date_to.")
    if (date_to - date_from).days + 1 > MAX_WINDOW_DAYS:
        raise invalid_argument(
            f"The window is longer than {MAX_WINDOW_DAYS} days.",
            hint="Search a shorter window and repeat it for the next one.",
        )
    text = query.strip()
    if len(text) < MIN_QUERY_LENGTH:
        raise invalid_argument(
            f"query must have at least {MIN_QUERY_LENGTH} characters.",
            hint="The Source reads the whole query as one phrase; use a longer term.",
        )
    alias = resolve_djen_court(court, date_to)
    key = "|".join((date_from.isoformat(), date_to.isoformat(), text, wanted or ""))
    number, skip = _resume_position(cursor, alias, key)
    chosen: list[Publication] = []
    dropped = 0
    reads = 0
    while True:
        page = await repository.search(alias, text, date_from, date_to, page=number)
        reads += 1
        decisions = [p for p in page.publications if p.kind is not PublicationKind.NOT_A_DECISION]
        dropped += len(page.publications) - len(decisions)
        available = [p for p in decisions if wanted is None or p.kind is wanted][skip:]
        room = limit - len(chosen)
        chosen.extend(available[:room])
        if len(available) > room:
            resume: tuple[int, int] | None = (number, skip + room)
            break
        skip = 0
        if not page.more or number >= MAX_DJEN_PAGE:
            resume = None
            break
        number += 1
        if len(chosen) >= limit or reads >= MAX_PAGES_PER_CALL:
            resume = (number, 0)
            break
    ceiling = resume is None and page.more
    return PublicationSearchResult(
        court=alias,
        publications=tuple(chosen),
        not_decisions_dropped=dropped,
        total=page.total,
        total_is_lower_bound=page.total >= COUNT_CAP,
        next_cursor=Cursor(alias, resume, key).encode() if resume else None,
        retrieved_at=page.retrieved_at,
        hint=(
            f"The Source stops after {MAX_DJEN_PAGE * 100} matches; narrow the window or the "
            "query to reach the rest."
            if ceiling
            else None
        ),
    )


def _resume_position(cursor: str | None, scope: str, key: str) -> tuple[int, int]:
    """Return the Source page and the number of its kept items already returned."""
    if cursor is None:
        return 1, 0
    decoded = Cursor.decode(cursor, scopes=(scope,))
    if decoded.filters_key != key:
        raise invalid_argument(
            "The cursor was issued for a different search.",
            hint="Repeat the same Court, window, query and kind, or start without a cursor.",
        )
    match decoded.position:
        case (int() as number, int() as skip) if 1 <= number <= MAX_DJEN_PAGE and skip >= 0:
            return number, skip
        case _:
            raise invalid_argument("The cursor is not valid.")


def _parse_kind(kind: str | None) -> PublicationKind | None:
    if kind is None:
        return None
    try:
        parsed = PublicationKind(kind.strip().lower())
    except ValueError:
        parsed = None
    if parsed is None or parsed is PublicationKind.NOT_A_DECISION:
        raise invalid_argument(
            f"Unknown kind: {kind!r}.",
            hint="Valid kinds: " + ", ".join(k.value for k in DECISION_KINDS),
        )
    return parsed
