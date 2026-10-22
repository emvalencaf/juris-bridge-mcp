"""Port: where Precedents come from."""

from typing import Protocol

from juris_bridge_mcp.domain.precedent import (
    PrecedentDecisions,
    PrecedentFilters,
    PrecedentPage,
    PrecedentRecord,
)


class PrecedentSource(Protocol):
    """Finds Precedents: a page by filters, one by id, and the decisions of one."""

    async def search(self, filters: PrecedentFilters, *, page: int, limit: int) -> PrecedentPage:
        """Return up to `limit` Precedents of the 1-based `page`."""
        ...

    async def find(self, precedent_id: str) -> PrecedentRecord | None:
        """Return the Precedent, or `None` when the Source holds none with that id."""
        ...

    async def decisions(self, precedent_id: str) -> PrecedentDecisions:
        """Return the decisions of a Precedent; they may be empty."""
        ...
