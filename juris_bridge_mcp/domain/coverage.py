"""What the server can answer, by Source and Court."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CourtCoverage:
    """One Court as a Source knows it."""

    alias: str
    supported: bool
    citation_url: bool = False


@dataclass(frozen=True)
class SourceCoverage:
    """One Source, the kind of data it serves and the Courts it covers."""

    source: str
    kind: str
    description: str
    courts: tuple[CourtCoverage, ...] = ()
