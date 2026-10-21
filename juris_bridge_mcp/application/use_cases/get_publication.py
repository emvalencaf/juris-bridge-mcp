"""Use case: read the full plain text of one Publication, in slices."""

import base64
import binascii
from dataclasses import dataclass
from datetime import UTC, date, datetime

from juris_bridge_mcp.domain.cnj_number import CnjNumber
from juris_bridge_mcp.domain.cursor import Cursor
from juris_bridge_mcp.domain.errors import ToolFailure, invalid_argument, not_found
from juris_bridge_mcp.domain.publication import SOURCE, Publication, PublicationSearch
from juris_bridge_mcp.domain.publication_courts import resolve_djen_court
from juris_bridge_mcp.ports.publication_repository import PublicationRepository

# Characters of text per slice; the text of an STJ or TRF4 Publication runs to about 68,000.
SLICE_CHARS = 10000
# Pages read at most while looking for the item among those of its Case and day.
MAX_PAGES = 5


@dataclass(frozen=True)
class PublicationText:
    """One slice of a Publication's plain text.

    `next_cursor` is set when `truncated`: pass it back with the same `id` to read the rest.
    """

    publication: Publication
    text: str
    truncated: bool
    next_cursor: str | None
    retrieved_at: datetime


def _invalid_id() -> ToolFailure:
    return invalid_argument(
        "The id is not valid.", hint="Pass the id exactly as search_publications returned it."
    )


def _parse_id(publication_id: str) -> tuple[str, date, CnjNumber, str]:
    """Return the Court, day, CNJ number and item hash an id carries, or raise."""
    try:
        raw = base64.urlsafe_b64decode(publication_id + "=" * (-len(publication_id) % 4)).decode()
        court, day, digits, item_hash = raw.split("|", 3)
        number = CnjNumber.parse(digits)
        parsed_day = date.fromisoformat(day)
    except (ValueError, binascii.Error, ToolFailure):
        raise _invalid_id() from None
    if not item_hash:
        raise _invalid_id()
    return court, parsed_day, number, item_hash


async def get_publication(
    repository: PublicationRepository,
    *,
    publication_id: str,
    cursor: str | None = None,
) -> PublicationText:
    """Return a slice of the Publication's text, cut at a space and chained by `cursor`.

    The DJEN has no read-by-id endpoint, so the narrow query the id carries (Court, day and
    CNJ number) is repeated and the item is picked by its hash; `not_found` when it is gone.
    """
    court, day, number, item_hash = _parse_id(publication_id)
    resolve_djen_court(court, day)
    offset = _offset(cursor, publication_id)
    found: Publication | None = None
    retrieved_at = datetime.now(UTC)
    for page_number in range(1, MAX_PAGES + 1):
        page = await repository.search(
            PublicationSearch(
                court=court,
                query="",
                date_from=day,
                date_to=day,
                page=page_number,
                cnj_number=number,
            )
        )
        retrieved_at = page.retrieved_at
        found = next((p for p in page.publications if p.item_hash == item_hash), None)
        if found is not None or not page.more or page.truncated:
            break
    if found is None:
        raise not_found(
            SOURCE,
            "The DJEN no longer returns this Publication.",
            "Search again with search_publications; the item may have been withdrawn.",
        )
    body = found.text
    if offset > 0 and offset >= len(body):
        raise invalid_argument("The cursor is not valid.")
    end = offset + SLICE_CHARS
    if end >= len(body):
        return PublicationText(found, body[offset:], False, None, retrieved_at)
    # The text has its whitespace collapsed to single spaces, so a space is a safe cut.
    cut = body.rfind(" ", offset + 1, end + 1)
    if cut == -1:
        cut = end
    resume = cut + 1 if body[cut] == " " else cut
    token = Cursor(SOURCE, (resume,), publication_id).encode()
    return PublicationText(found, body[offset:cut], True, token, retrieved_at)


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
