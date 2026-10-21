"""Use case: read the full plain text of one Publication, in slices."""

from dataclasses import dataclass
from datetime import UTC, datetime

from juris_bridge_mcp.domain.cursor import Cursor
from juris_bridge_mcp.domain.errors import ErrorCode, invalid_argument, not_found, source_failure
from juris_bridge_mcp.domain.publication import (
    SOURCE,
    Publication,
    PublicationRef,
    PublicationSearch,
)
from juris_bridge_mcp.domain.publication_courts import resolve_djen_court
from juris_bridge_mcp.ports.publication_repository import PublicationRepository

# Characters of text per slice; the text of an STJ or TRF4 Publication runs to about 68,000.
SLICE_CHARS = 10000
# Pages read at most while looking for the item among those of its Case and day.
MAX_PAGES = 5


@dataclass(frozen=True)
class PublicationText:
    """One slice of a Publication's plain text.

    `next_cursor` is set when more follows (`truncated`): pass it back with the same `id`.
    """

    publication: Publication
    text: str
    next_cursor: str | None
    retrieved_at: datetime

    @property
    def truncated(self) -> bool:
        """Return whether more of the text follows this slice."""
        return self.next_cursor is not None


async def get_publication(
    repository: PublicationRepository,
    *,
    publication_id: str,
    cursor: str | None = None,
) -> PublicationText:
    """Return a slice of the Publication's text, cut at a space and chained by `cursor`.

    The DJEN has no read-by-id endpoint, so the narrow query the id carries (Court, day and
    CNJ number) is repeated and the item is picked by its hash; `not_found` when it is gone,
    and a `source_unavailable` failure when the Source gave up before the item could be found.
    """
    ref = PublicationRef.decode(publication_id)
    resolve_djen_court(ref.court, ref.day)
    offset = _offset(cursor, publication_id)
    publication, retrieved_at = await _find(repository, ref)
    text = publication.text
    if offset > 0 and offset >= len(text):
        raise invalid_argument("The cursor is not valid.")
    cut, resume = _cut(text, offset)
    token = Cursor(SOURCE, (resume,), publication_id).encode() if resume < len(text) else None
    return PublicationText(publication, text[offset:cut], token, retrieved_at)


async def _find(
    repository: PublicationRepository, ref: PublicationRef
) -> tuple[Publication, datetime]:
    """Return the item `ref` names and when it was read."""
    retrieved_at = datetime.now(UTC)
    gave_up = False
    for page_number in range(1, MAX_PAGES + 1):
        page = await repository.search(
            PublicationSearch(
                court=ref.court,
                query="",
                date_from=ref.day,
                date_to=ref.day,
                page=page_number,
                cnj_number=ref.number,
            )
        )
        retrieved_at = page.retrieved_at
        for candidate in page.publications:
            if candidate.item_hash == ref.item_hash:
                return candidate, retrieved_at
        gave_up = page.truncated or (page.more and page_number == MAX_PAGES)
        if not page.more or page.truncated:
            break
    if gave_up:
        raise source_failure(
            SOURCE,
            ErrorCode.SOURCE_UNAVAILABLE,
            "The DJEN stopped answering before this Publication could be located.",
            retryable=False,
            hint="This is not proof that it is gone; search again with search_publications.",
        )
    raise not_found(
        SOURCE,
        "The DJEN no longer returns this Publication.",
        "Search again with search_publications; the item may have been withdrawn.",
    )


def _cut(text: str, offset: int) -> tuple[int, int]:
    """Return where the slice from `offset` ends and where the next one starts.

    The text has its whitespace collapsed to single spaces, so a space is a safe cut; a text
    with none in reach is cut at the limit.
    """
    limit = offset + SLICE_CHARS
    if limit >= len(text):
        return len(text), len(text)
    space = text.rfind(" ", offset + 1, limit + 1)
    if space == -1:
        return limit, limit
    return space, space + 1


def _offset(cursor: str | None, publication_id: str) -> int:
    if cursor is None:
        return 0
    decoded = Cursor.decode(cursor, scopes=(SOURCE,))
    if decoded.filters_key != publication_id:
        raise invalid_argument(
            "The cursor was issued for a different Publication.",
            hint="Repeat the same id, or start again without a cursor.",
        )
    return decoded.offset()
