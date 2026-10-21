"""A Publication as the DJEN released it, and what one page of a search holds."""

import base64
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from juris_bridge_mcp.domain.cnj_number import CnjNumber
from juris_bridge_mcp.domain.publication_kind import PublicationKind

SOURCE = "djen"

# The DJEN stops counting matches here, so a total at this value is a lower bound.
COUNT_CAP = 10000


@dataclass(frozen=True)
class Relevance:
    """How a Publication fits the query among the others of its page.

    `score` is a BM25 value that only means something within the page it was computed in.
    `matched_terms` are the query terms found in the text, as typed.
    """

    score: float
    matched_terms: tuple[str, ...]


@dataclass(frozen=True)
class Publication:
    """One item of a Diário, with a plain-text excerpt of its text.

    `document_type` is the raw `tipoDocumento`, free text that differs per Court.
    `url` is set only when the item carries a link to its own content.
    `kind` is our heuristic classification (see `publication_kind`); `NOT_A_DECISION` items
    are kept here so they can be counted, and never presented.
    `item_hash` is the DJEN's hash of the item, which tells it apart from the others of the
    same Court, day and Case. `organ_id` is the DJEN's id of the issuing body, when it gives one.
    `text` is the whole plain text, kept so a search can filter on it; it is never presented.
    `relevance` is set by a search (see `publication_ranking`).
    """

    court: str
    day: date
    number: CnjNumber
    document_type: str | None
    excerpt: str
    text_length: int
    item_hash: str
    kind: PublicationKind
    url: str | None = None
    organ_id: int | None = None
    text: str = field(default="", repr=False, compare=False)
    relevance: Relevance | None = None

    @property
    def id(self) -> str:
        """Return the opaque id: Court, day, CNJ number and item hash."""
        raw = "|".join((self.court, self.day.isoformat(), self.number.digits, self.item_hash))
        return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")

    @property
    def citation_text(self) -> str:
        """Return the human-readable reference to the item."""
        kind = f"{self.document_type}, " if self.document_type else ""
        return (
            f"{self.court.upper()}, {kind}proc. {self.number.formatted}, "
            f"publicada em {self.day:%d/%m/%Y} (DJEN)"
        )


@dataclass(frozen=True)
class PublicationSearch:
    """One request to the Source: a Court's Publications released in a window of days.

    `query` is sent as the Source's text, or left out when empty. `page` counts from 1.
    `organ_id` narrows the slice to one issuing body and `cnj_number` to one Case.
    """

    court: str
    query: str
    date_from: date
    date_to: date
    page: int = 1
    organ_id: int | None = None
    cnj_number: CnjNumber | None = None


@dataclass(frozen=True)
class PublicationPage:
    """One page of a search, newest first as the DJEN returns it, before any filtering.

    `total` is the DJEN's own count, capped at `COUNT_CAP`. `more` is true when matches
    follow this page. `truncated` is true when the DJEN gave up past its depth ceiling, so
    nothing more can be read of the slice. `requests` is how many requests the page cost, a
    429 waited out and asked again counting twice.
    """

    publications: tuple[Publication, ...]
    total: int
    more: bool = False
    truncated: bool = False
    requests: int = 1
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def organ_ids(self) -> tuple[int, ...]:
        """Return the distinct bodies the page's items came from, in order of appearance."""
        return tuple(dict.fromkeys(p.organ_id for p in self.publications if p.organ_id is not None))
