"""A Case as DataJud describes it: metadata and movements, never parties or judges."""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from juris_bridge_mcp.domain.cnj_number import CnjNumber


@dataclass(frozen=True)
class CodedTerm:
    """A TPU (Tabelas Processuais Unificadas) term: its code and untranslated Portuguese name."""

    code: int | None
    name: str | None


@dataclass(frozen=True)
class EventComplement:
    """A tabulated detail of a movement, such as the kind of hearing."""

    term: CodedTerm
    kind: str | None
    value: int | str | None


@dataclass(frozen=True)
class CaseEvent:
    """One movement (_movimento_) in the Case timeline."""

    term: CodedTerm
    occurred_at: datetime | None
    judging_body: CodedTerm | None = None
    complements: tuple[EventComplement, ...] = ()


@dataclass(frozen=True)
class Case:
    """A judicial proceeding registered in a Court."""

    number: CnjNumber
    court: str
    instance: str | None = None
    filed_on: date | None = None
    case_class: CodedTerm | None = None
    subjects: tuple[CodedTerm, ...] = ()
    judging_body: CodedTerm | None = None
    secrecy_level: int | None = None
    source_system: CodedTerm | None = None
    last_updated_at: datetime | None = None
    events: tuple[CaseEvent, ...] = ()


@dataclass(frozen=True)
class CaseRecord:
    """A Case with the unstable upstream payload it came from.

    `matches` is how many records the Source held for the number (one per instance);
    `retrieved_at` is when the Source was asked, which stays true when a cache serves it.
    """

    case: Case
    raw: dict[str, Any] = field(default_factory=dict)
    matches: int = 1
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(UTC))
