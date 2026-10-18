"""Port: where Norms come from."""

from typing import Protocol

from juris_bridge_mcp.domain.legislation import LegislationFilters, LegislationPage


class LegislationRepository(Protocol):
    """Finds Norms by type, number and year."""

    async def search(
        self, filters: LegislationFilters, *, limit: int, offset: int = 0
    ) -> LegislationPage:
        """Return up to `limit` Norms in a stable order, skipping the first `offset`."""
        ...
