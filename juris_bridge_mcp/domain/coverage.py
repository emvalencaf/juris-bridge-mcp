"""What the server can answer, by Source and Court."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class CourtCoverage:
    """One Court as a Source knows it."""

    alias: str
    supported: bool
    citation_url: bool = False
    available_from: date | None = None
    reason: str | None = None


@dataclass(frozen=True)
class SourceCoverage:
    """One Source, the kind of data it serves and the Courts it covers."""

    source: str
    kind: str
    description: str
    courts: tuple[CourtCoverage, ...] = ()
