"""What a Case search asks for and what one page of it holds."""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from juris_bridge_mcp.domain.case import Case


@dataclass(frozen=True)
class CaseFilters:
    """The only filters a search offers; there are none on parties, judges or CPF."""

    case_class: int | None = None
    judging_body: int | None = None
    subject: int | None = None
    filed_from: date | None = None
    filed_to: date | None = None

    def key(self) -> str:
        """Return a short stable fingerprint, so a Cursor can tell the filters changed."""
        parts = (self.case_class, self.judging_body, self.subject, self.filed_from, self.filed_to)
        return ",".join("" if p is None else str(p) for p in parts)


@dataclass(frozen=True)
class CasePage:
    """One page of a search, in the Source's stable order.

    `next_position` is the Source's sort position of the last item when more follow.
    `total_is_lower_bound` is true when the Source stopped counting at its cap.
    """

    cases: tuple[Case, ...]
    total: int
    total_is_lower_bound: bool
    next_position: tuple[int | str, int | str] | None = None
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(UTC))
