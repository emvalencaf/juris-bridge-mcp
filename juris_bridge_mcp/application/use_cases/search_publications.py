"""Use case: search the Publications of a Court released in a window of days."""

from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum

from juris_bridge_mcp.domain.cursor import Cursor
from juris_bridge_mcp.domain.errors import invalid_argument
from juris_bridge_mcp.domain.publication import COUNT_CAP, Publication, PublicationPage
from juris_bridge_mcp.domain.publication_courts import resolve_djen_court
from juris_bridge_mcp.domain.publication_kind import DECISION_KINDS, PublicationKind
from juris_bridge_mcp.ports.publication_repository import PublicationRepository

DEFAULT_LIMIT = 10
MAX_LIMIT = 25
MAX_WINDOW_DAYS = 31
# The DJEN answers a page of 100 and gives up past its undocumented depth ceiling, which is
# also where its count stops (`COUNT_CAP`).
MAX_DJEN_PAGE = COUNT_CAP // 100
# Requests to the Source for one call, so a quiet window or a filter that keeps little cannot
# fan out without end; the Cursor carries the search on.
MAX_REQUESTS_PER_CALL = 10
# The DJEN answers a trimmed query shorter than this with a misleading HTTP 500.
MIN_QUERY_LENGTH = 5


class IncompleteReason(StrEnum):
    """Why a search did not cover the whole window."""

    BUDGET = "budget"
    SLICE_CAP = "slice_cap"
    DEPTH_CEILING = "depth_ceiling"


_HINTS = {
    IncompleteReason.BUDGET: "More follows: pass next_cursor to read on.",
    IncompleteReason.SLICE_CAP: (
        f"A day matched {COUNT_CAP} or more items, where the Source stops counting; it was "
        "split by issuing body from the ids seen on its first page, so some may be missing. "
        "Narrow the query to reach them."
    ),
    IncompleteReason.DEPTH_CEILING: (
        f"The Source stops after about {MAX_DJEN_PAGE * 100} matches of a slice; narrow the "
        "query to reach the rest."
    ),
}


@dataclass(frozen=True)
class PublicationSearchResult:
    """A page of Publications ready to present.

    `complete` is true when the search reached the end of the window without the Source
    truncating a slice; otherwise `incomplete_reason` says why: `budget` (more follows, see
    `next_cursor`), `slice_cap` or `depth_ceiling`.
    """

    court: str
    publications: tuple[Publication, ...]
    complete: bool
    incomplete_reason: IncompleteReason | None
    next_cursor: str | None
    retrieved_at: datetime
    not_decisions_dropped: int = 0
    hint: str | None = None


@dataclass(frozen=True)
class _Position:
    """Where a search is: a day, the issuing bodies still to read (first is current), a page.

    `skip` is how many kept items of the page were already returned.
    """

    day: date
    organs: tuple[int, ...] = ()
    page: int = 1
    skip: int = 0

    def next_slice(self, date_from: date) -> "_Position | None":
        """Return the position of the next slice, or `None` past the oldest day."""
        if self.organs[1:]:
            return _Position(self.day, self.organs[1:])
        day = self.day - timedelta(days=1)
        return _Position(day) if day >= date_from else None

    def encode(self, scope: str, key: str, truncation: IncompleteReason | None) -> str:
        """Return the Cursor token for this position and the truncation met so far."""
        organs = ",".join(str(organ) for organ in self.organs)
        parts = (self.day.isoformat(), organs, self.page, self.skip, truncation or "")
        return Cursor(scope, parts, key).encode()

    @classmethod
    def decode(
        cls, token: str, scope: str, key: str, date_from: date, date_to: date
    ) -> "tuple[_Position, IncompleteReason | None]":
        """Parse a token issued for this search, or raise `invalid_argument`."""
        decoded = Cursor.decode(token, scopes=(scope,))
        if decoded.filters_key != key:
            raise invalid_argument(
                "The cursor was issued for a different search.",
                hint="Repeat the same Court, window, query and kind, or start without a cursor.",
            )
        try:
            match decoded.position:
                case (str() as day, str() as organs, int() as page, int() as skip, str() as met):
                    position = cls(
                        date.fromisoformat(day),
                        tuple(int(organ) for organ in organs.split(",")) if organs else (),
                        page,
                        skip,
                    )
                    truncation = IncompleteReason(met) if met else None
                case _:
                    raise ValueError
        except ValueError:
            raise invalid_argument("The cursor is not valid.") from None
        if (
            not date_from <= position.day <= date_to
            or not 1 <= page <= MAX_DJEN_PAGE
            or skip < 0
            or truncation is IncompleteReason.BUDGET
            or any(organ <= 0 for organ in position.organs)
        ):
            raise invalid_argument("The cursor is not valid.")
        return position, truncation


def _advance(
    position: _Position, page: PublicationPage, date_from: date
) -> tuple[_Position | None, IncompleteReason | None]:
    """Return where to read next once `page` is spent, and the truncation met leaving it."""
    if page.more and position.page < MAX_DJEN_PAGE:
        return replace(position, page=position.page + 1, skip=0), None
    met = IncompleteReason.DEPTH_CEILING if page.more else None
    return position.next_slice(date_from), met


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
    invalid. Despachos, intimações and editais are dropped from what the Source answers, and
    `kind`, when given, keeps only that kind; without it every decision stays, `ambiguous`
    included. The window is walked one day at a time from `date_to` back, a day matching
    `COUNT_CAP` items being split by issuing body, and at most `MAX_REQUESTS_PER_CALL` requests
    are made; `next_cursor` resumes where the call stopped and must come back with the same
    Court, window, query and kind.
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
    position: _Position | None = _Position(date_to)
    truncation: IncompleteReason | None = None
    if cursor is not None:
        position, truncation = _Position.decode(cursor, alias, key, date_from, date_to)
    chosen: list[Publication] = []
    dropped = 0
    requests = 0
    retrieved_at = None
    while position is not None and len(chosen) < limit and requests < MAX_REQUESTS_PER_CALL:
        page = await repository.search(
            alias,
            text,
            position.day,
            position.day,
            page=position.page,
            organ_id=position.organs[0] if position.organs else None,
        )
        requests += page.requests
        retrieved_at = page.retrieved_at
        if page.truncated:
            truncation = truncation or IncompleteReason.DEPTH_CEILING
            position = position.next_slice(date_from)
            continue
        if position.page == 1 and page.total >= COUNT_CAP:
            truncation = truncation or IncompleteReason.SLICE_CAP
            if not position.organs and page.organ_ids:
                position = _Position(position.day, page.organ_ids)
                continue
        decisions = [p for p in page.publications if p.kind is not PublicationKind.NOT_A_DECISION]
        dropped += len(page.publications) - len(decisions)
        available = [p for p in decisions if wanted is None or p.kind is wanted][position.skip :]
        room = limit - len(chosen)
        chosen.extend(available[:room])
        if len(available) > room:
            position = replace(position, skip=position.skip + room)
            continue
        position, met = _advance(position, page, date_from)
        truncation = truncation or met
    incomplete = IncompleteReason.BUDGET if position is not None else truncation
    return PublicationSearchResult(
        court=alias,
        publications=tuple(chosen),
        complete=incomplete is None,
        incomplete_reason=incomplete,
        next_cursor=position.encode(alias, key, truncation) if position else None,
        retrieved_at=retrieved_at or datetime.now(UTC),
        not_decisions_dropped=dropped,
        hint=_HINTS[incomplete] if incomplete else None,
    )


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
