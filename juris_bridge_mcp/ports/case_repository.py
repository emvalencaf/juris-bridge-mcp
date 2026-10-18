"""Port: where Cases come from."""

from typing import Protocol

from juris_bridge_mcp.domain.case import CaseRecord
from juris_bridge_mcp.domain.cnj_number import CnjNumber


class CaseRepository(Protocol):
    """Finds one Case by its CNJ number in one Court."""

    async def find(self, number: CnjNumber, court: str) -> CaseRecord | None:
        """Return the Case, or `None` when the Source holds nothing for the number."""
        ...
