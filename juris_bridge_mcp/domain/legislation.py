"""A federal norm as the Senado catalogues it, and what a search for one asks for."""

import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure, invalid_argument

SOURCE = "senado"

_URN = re.compile(r"urn:lex:br:federal:([a-z.]+):(\d{4}-\d{2}-\d{2});(\d+)")

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
class Urn:
    """The URN Lex of a federal norm, split into the parts it is built from."""

    text: str
    norm_type: str
    signed_on: date
    number: int

    @classmethod
    def parse(cls, raw: str) -> "Urn":
        """Parse `raw`, or raise `invalid_argument`.

        `norm_type` is the agent-facing key when the URN type is a searchable one, else the raw
        URN type (the Senado also catalogues acts such as `mensagem`).
        """
        text = raw.strip()
        match = _URN.fullmatch(text)
        if match is None:
            raise invalid_argument(
                f"'{raw}' is not a federal URN Lex.",
                hint="Use a urn from search_legislation, e.g. urn:lex:br:federal:lei:2021-04-01;1.",
            )
        urn_type, day, number = match.groups()
        try:
            signed_on = date.fromisoformat(day)
        except ValueError:
            raise invalid_argument(f"'{raw}' has an impossible date.") from None
        keys = {lex: key for key, (_, lex) in NORM_TYPES.items()}
        return cls(text, keys.get(urn_type, urn_type), signed_on, int(number))


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
class Publication:
    """Where a norm was published (the Diário Oficial edition, page and column)."""

    kind: str
    edition: str
    published_on: date | None
    page: str | None = None
    column: str | None = None


@dataclass(frozen=True)
class Relation:
    """A later norm that acts on this one: amends, regulates, vetoes or relates to it."""

    kind: str
    name: str
    signed_on: date | None
    norm_id: str


@dataclass(frozen=True)
class NormRecord:
    """A Norm with its publications and every relation, plus the unstable upstream payload."""

    norm: Norm
    publications: tuple[Publication, ...]
    relations: tuple[Relation, ...]
    raw: dict[str, Any]
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def latest_relations(self) -> tuple[Relation, ...]:
        """Return each related norm once per kind, newest first.

        The Senado repeats a relation once per affected provision; those collapse here.
        """
        distinct = {(r.norm_id, r.kind): r for r in self.relations}.values()
        return tuple(sorted(distinct, key=lambda r: r.signed_on or date.min, reverse=True))


@dataclass(frozen=True)
class LegislationPage:
    """One page of a search; `next_offset` is set when more norms follow."""

    norms: tuple[Norm, ...]
    total: int
    next_offset: int | None = None
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(UTC))
