"""Port: where the Coverage statement comes from."""

from typing import Protocol

from juris_bridge_mcp.modules.coverage.domain.coverage import SourceCoverage


class CoverageCatalog(Protocol):
    """Provides the static Coverage of every Source; never touches the network."""

    def sources(self) -> tuple[SourceCoverage, ...]: ...
