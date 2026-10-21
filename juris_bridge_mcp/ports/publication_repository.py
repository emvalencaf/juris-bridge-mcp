"""Port: where Publications come from."""

from typing import Protocol

from juris_bridge_mcp.domain.publication import PublicationPage, PublicationSearch


class PublicationRepository(Protocol):
    """Finds the Publications of one Court released in a window of days."""

    async def search(self, request: PublicationSearch) -> PublicationPage:
        """Return page `request.page` (from 1, 100 items) of the Publications it asks for.

        A page past the Source's depth ceiling comes back `truncated` instead of failing.

        Every kind of item comes back, each with its classified `kind`; filtering is the caller's.
        """
        ...
