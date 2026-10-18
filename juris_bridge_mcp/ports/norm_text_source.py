"""Port: where the text of a Norm comes from."""

from typing import Protocol

from juris_bridge_mcp.domain.legislation import Urn
from juris_bridge_mcp.domain.legislation_text import NormText


class NormTextSource(Protocol):
    """Fetches the plain text of a Norm, with its articles located."""

    async def fetch(self, urn: Urn) -> NormText | None:
        """Return the text, or `None` when the Source has no page for this Norm."""
        ...
