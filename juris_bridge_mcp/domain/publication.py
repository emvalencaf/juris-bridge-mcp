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
class Publication:
    """One item of a Diário, with a plain-text excerpt of its text.

    `document_type` is the raw `tipoDocumento`, free text that differs per Court.
    `url` is set only when the item carries a link to its own content.
    `kind` is our heuristic classification (see `publication_kind`); `NOT_A_DECISION` items
    are kept here so they can be counted, and never presented.
    `item_hash` is the DJEN's hash of the item, which tells it apart from the others of the
    same Court, day and Case.
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
class PublicationPage:
    """One page of a search, newest first as the DJEN returns it, before any filtering.

    `total` is the DJEN's own count, capped at `COUNT_CAP`. `more` is true when matches
    follow this page.
    """

    publications: tuple[Publication, ...]
    total: int
    more: bool = False
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(UTC))
