"""Port: where Publications come from."""

from datetime import date
from typing import Protocol

from juris_bridge_mcp.domain.publication import PublicationPage


class PublicationRepository(Protocol):
    """Finds the Publications of one Court released in a window of days."""

    async def search(
        self, court: str, query: str, date_from: date, date_to: date, *, limit: int
    ) -> PublicationPage:
        """Return up to `limit` Publications whose text matches `query` as the Source reads it."""
        ...
