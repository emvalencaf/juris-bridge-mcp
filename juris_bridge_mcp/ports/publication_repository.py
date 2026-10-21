"""Port: where Publications come from."""

from datetime import date
from typing import Protocol

from juris_bridge_mcp.domain.publication import PublicationPage


class PublicationRepository(Protocol):
    """Finds the Publications of one Court released in a window of days."""

    async def search(
        self, court: str, query: str, date_from: date, date_to: date, *, page: int = 1
    ) -> PublicationPage:
        """Return page `page` (from 1, 100 items) of the Publications matching `query`.

        Every kind of item comes back, each with its classified `kind`; filtering is the caller's.
        """
        ...
