"""A federal norm as the Senado catalogues it, and what a search for one asks for."""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure

SOURCE = "senado"

# Agent-facing type -> (Senado `tipo` sigla, URN Lex type).
NORM_TYPES = {
    "lei": ("LEI", "lei"),
    "lei-complementar": ("LCP", "lei.complementar"),
    "decreto": ("DEC", "decreto"),
    "decreto-lei": ("DEL", "decreto.lei"),
    "medida-provisoria": ("MPV", "medida.provisoria"),
    "emenda-constitucional": ("EMC", "emenda.constitucional"),
}


def resolve_norm_type(raw: str) -> str:
    """Return the canonical type key, or raise `invalid_argument` listing the valid ones."""
    key = raw.strip().lower().replace("_", "-").replace(" ", "-")
    if key not in NORM_TYPES:
        raise ToolFailure(
            ErrorCode.INVALID_ARGUMENT,
            f"Unknown norm type '{raw}'.",
            source=None,
            retryable=False,
            hint=f"Use one of: {', '.join(NORM_TYPES)}.",
        )
    return key


def norm_urn(norm_type: str, signed_on: date, number: int) -> str:
    """Build the URN Lex of a federal norm, e.g. `urn:lex:br:federal:lei:2021-04-01;14133`."""
    return f"urn:lex:br:federal:{NORM_TYPES[norm_type][1]}:{signed_on.isoformat()};{number}"


@dataclass(frozen=True)
class LegislationFilters:
    """The only filters a search offers; the Senado has no free-text search."""

    norm_type: str
    number: int | None = None
    year: int | None = None

    def key(self) -> str:
        """Return a short stable fingerprint, so a Cursor can tell the filters changed."""
        return ",".join(
            "" if p is None else str(p) for p in (self.norm_type, self.number, self.year)
        )


@dataclass(frozen=True)
class Norm:
    """A norm (statute or other normative act), described but never quoted."""

    urn: str
    norm_type: str
    number: int
    year: int
    signed_on: date
    name: str
    summary: str | None = None
    nickname: str | None = None
    citation_url: str | None = None


@dataclass(frozen=True)
class LegislationPage:
    """One page of a search; `next_offset` is set when more norms follow."""

    norms: tuple[Norm, ...]
    total: int
    next_offset: int | None = None
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(UTC))
