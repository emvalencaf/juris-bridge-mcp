"""Port: where Cases come from."""

from typing import Protocol

from juris_bridge_mcp.domain.case import CaseRecord
from juris_bridge_mcp.domain.case_search import CaseFilters, CasePage
from juris_bridge_mcp.domain.cnj_number import CnjNumber


class CaseRepository(Protocol):
    """Finds Cases in one Court: one by CNJ number, or a page by filters."""

    async def find(self, number: CnjNumber, court: str) -> CaseRecord | None:
        """Return the Case, or `None` when the Source holds nothing for the number."""
        ...

    async def search(
        self,
        court: str,
        filters: CaseFilters,
        *,
        limit: int,
        after: tuple[int | str, int | str] | None = None,
    ) -> CasePage:
        """Return up to `limit` Cases in a stable order, starting after the `after` position."""
        ...
