"""Use case: search the Publications of a Court released in a window of days."""

from dataclasses import dataclass
from datetime import date, datetime

from juris_bridge_mcp.domain.errors import invalid_argument
from juris_bridge_mcp.domain.publication import COUNT_CAP, Publication
from juris_bridge_mcp.domain.publication_courts import resolve_djen_court
from juris_bridge_mcp.domain.publication_kind import DECISION_KINDS, PublicationKind
from juris_bridge_mcp.ports.publication_repository import PublicationRepository

DEFAULT_LIMIT = 10
MAX_LIMIT = 25
MAX_WINDOW_DAYS = 31
# The DJEN answers a trimmed query shorter than this with a misleading HTTP 500.
MIN_QUERY_LENGTH = 5


@dataclass(frozen=True)
class PublicationSearchResult:
    """A page of Publications ready to present."""

    court: str
    publications: tuple[Publication, ...]
    total: int
    total_is_lower_bound: bool
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
) -> PublicationSearchResult:
    """Return the first Publications of the Court in the window whose text matches `query`.

    The query goes to the Source as it is, trimmed; nothing is called when an argument is
    invalid. Despachos, intimações and editais are dropped from the page the Source answers
    (the `total` still counts them), and `kind`, when given, keeps only that kind; without it
    every decision stays, `ambiguous` included.
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
    page = await repository.search(alias, text, date_from, date_to)
    decisions = tuple(p for p in page.publications if p.kind is not PublicationKind.NOT_A_DECISION)
    matching = tuple(p for p in decisions if wanted is None or p.kind is wanted)
    hint = None
    if page.more or len(matching) > limit:
        hint = (
            "More Publications match than this page holds; narrow the window or the query. "
            "The Source ranks nothing and this tool does not page yet."
        )
    return PublicationSearchResult(
        court=alias,
        publications=matching[:limit],
        not_decisions_dropped=len(page.publications) - len(decisions),
        total=page.total,
        total_is_lower_bound=page.total >= COUNT_CAP,
        retrieved_at=page.retrieved_at,
        hint=hint,
    )


def _parse_kind(kind: str | None) -> PublicationKind | None:
    if kind is None:
        return None
    try:
        parsed = PublicationKind(kind.strip().lower())
    except ValueError:
        parsed = PublicationKind.NOT_A_DECISION
    if parsed is PublicationKind.NOT_A_DECISION:
        raise invalid_argument(
            f"Unknown kind: {kind!r}.",
            hint="Valid kinds: " + ", ".join(k.value for k in DECISION_KINDS),
        )
    return parsed
