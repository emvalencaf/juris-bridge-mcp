"""What the server can answer, by Source and Court."""

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class CourtCoverage:
    """One Court as a Source knows it."""

    alias: str
    supported: bool
    citation_url: bool = False
    available_from: date | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """The wire form; `available_from` and `reason` are left out when not known."""
        out: dict[str, Any] = {
            "alias": self.alias,
            "supported": self.supported,
            "citation_url": self.citation_url,
        }
        if self.available_from is not None:
            out["available_from"] = self.available_from.isoformat()
        if self.reason is not None:
            out["reason"] = self.reason
        return out


@dataclass(frozen=True)
class SourceCoverage:
    """One Source, the kind of data it serves and the Courts it covers."""

    source: str
    kind: str
    description: str
    courts: tuple[CourtCoverage, ...] = ()
