"""Port: where Norms come from."""

from typing import Protocol

from juris_bridge_mcp.domain.legislation import LegislationFilters, LegislationPage, NormRecord


class LegislationRepository(Protocol):
    """Finds Norms by type, number and year, or one by URN Lex."""

    async def search(
        self, filters: LegislationFilters, *, limit: int, offset: int = 0
    ) -> LegislationPage:
        """Return up to `limit` Norms in a stable order, skipping the first `offset`."""
        ...

    async def find(self, urn: str) -> NormRecord | None:
        """Return the Norm with its publications and relations, or `None` when unknown."""
        ...
