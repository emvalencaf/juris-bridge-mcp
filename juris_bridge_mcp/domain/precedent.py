"""A Precedent as the BNP records it, and what one page of a search holds."""

import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from urllib.parse import urlencode

from juris_bridge_mcp.domain.cnj_number import CnjNumber
from juris_bridge_mcp.domain.errors import ToolFailure, invalid_argument

SOURCE = "bnp"

# The public page of the BNP app; it opens one Precedent from these query parameters, which is
# the link its own "copy link" button builds.
PUBLIC_PAGE = "https://bnp.pdpj.jus.br/pesquisa"

# The BNP stops counting matches here, so a total at this value is a lower bound.
COUNT_CAP = 10000

# Precedent kinds the BNP lists (its `especies`); a new one is added here when it appears.
KINDS = (
    "SUM", "SV", "OJ", "IAC", "IRDR", "SIRDR", "PN", "IRR", "RR", "RG", "ADI", "ADC", "ADO",
    "ADPF", "PUIL", "CT", "NT", "NTA", "ENU", "RC",
)  # fmt: skip

_ID = re.compile(r"^[a-z0-9_]+-[a-z0-9_]+-[a-z0-9_]+$")


def resolve_kind(value: str) -> str:
    """Return the canonical sigla of a Precedent kind, or raise `invalid_argument`."""
    key = value.strip().upper()
    if key not in KINDS:
        raise invalid_argument(
            f"Unknown precedent kind: {value!r}", hint="Valid kinds: " + ", ".join(KINDS)
        )
    return key


def parse_id(value: str) -> str:
    """Return a Precedent id (`<body>-<kind>-<number>`, lowercase), or raise `invalid_argument`."""
    key = value.strip().lower()
    if not _ID.match(key):
        raise invalid_argument(
            f"Not a precedent id: {value!r}",
            hint="Pass the id a search returned, such as stf-rg-1002.",
        )
    return key


@dataclass(frozen=True)
class StatusEntry:
    """One step of a Precedent's status history, with the dates the BNP gave for it."""

    status: str
    recorded_at: datetime | None = None
    admitted_on: date | None = None
    judged_on: date | None = None
    published_on: date | None = None


@dataclass(frozen=True)
class LeadingCase:
    """A paradigm case of a Precedent.

    `cnj_number` is set only when `raw_number` holds a valid CNJ number; an STF incident
    number, for one, stays in `raw_number` alone.
    """

    raw_number: str
    cnj_number: CnjNumber | None = None
    case_class: int | None = None
    url: str | None = None

    @classmethod
    def from_raw(
        cls, raw_number: str, *, case_class: int | None = None, url: str | None = None
    ) -> "LeadingCase":
        """Build a leading Case, linking a CNJ number only when `raw_number` is a valid one."""
        try:
            cnj = CnjNumber.parse(raw_number)
        except ToolFailure:
            cnj = None
        return cls(raw_number=raw_number, cnj_number=cnj, case_class=case_class, url=url)


@dataclass(frozen=True)
class Suspension:
    """A stay (_sobrestamento_) of the Cases that depend on a Precedent."""

    active: bool | None = None
    started_on: date | None = None
    description: str | None = None


@dataclass(frozen=True)
class Precedent:
    """A thesis-fixing record of the BNP.

    `court` is the project alias of `body`, or `None` when the body has none (such as TNU).
    `status` is the Source's own text. `matched_terms` are what the search highlighted.
    """

    id: str
    body: str
    court: str | None
    kind: str
    number: str
    question: str | None = None
    thesis: str | None = None
    status: str | None = None
    status_history: tuple[StatusEntry, ...] = ()
    leading_cases: tuple[LeadingCase, ...] = ()
    suspensions: tuple[Suspension, ...] = ()
    updated_on: date | None = None
    matched_terms: tuple[str, ...] = ()


def public_url(precedent: Precedent) -> str:
    """Return the link that opens the Precedent in the BNP's public app."""
    query = {"orgao": precedent.body.lower(), "tipo": precedent.kind, "nr": precedent.number}
    return f"{PUBLIC_PAGE}?{urlencode(query)}"


@dataclass(frozen=True)
class PrecedentDecisions:
    """The decisions the BNP shows for a Precedent; `texts` is often empty."""

    reporter: str | None = None
    tracking_url: str | None = None
    texts: tuple[str, ...] = ()


@dataclass(frozen=True)
class PrecedentFilters:
    """What a search asks for; `query` uses the BNP syntax (`+word`, `"phrase"`, `-word`)."""

    query: str | None = None
    court: str | None = None
    kind: str | None = None
    number: str | None = None
    updated_from: date | None = None
    updated_to: date | None = None
    include_cancelled: bool = False

    def key(self) -> str:
        """Return a short stable fingerprint, so a Cursor can tell the filters changed."""
        parts = (
            self.query,
            self.court,
            self.kind,
            self.number,
            self.updated_from,
            self.updated_to,
            self.include_cancelled,
        )
        return ",".join("" if p is None else str(p) for p in parts)


@dataclass(frozen=True)
class PrecedentPage:
    """One page of a search, with how many matched overall.

    `total_is_capped` is true when the Source stopped counting at `COUNT_CAP`.
    """

    precedents: tuple[Precedent, ...]
    total: int
    total_is_capped: bool
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class PrecedentRecord:
    """A Precedent as fetched, with when the Source was asked."""

    precedent: Precedent
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(UTC))
