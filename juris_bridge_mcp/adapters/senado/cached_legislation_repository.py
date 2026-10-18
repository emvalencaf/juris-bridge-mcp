"""A `LegislationRepository` that remembers a search across its pages, behind the `Cache` port."""

import sys
from dataclasses import replace

from juris_bridge_mcp.adapters import wide_event
from juris_bridge_mcp.domain.legislation import LegislationFilters, LegislationPage, NormRecord, Urn
from juris_bridge_mcp.ports.cache import Cache
from juris_bridge_mcp.ports.legislation_repository import LegislationRepository


class CachedLegislationRepository:
    """Wraps a repository; the whole match list is kept per filters and sliced into pages.

    The Senado has no paging, so every page of a search would otherwise repeat the full
    request. `retrieved_at` stays that of the request that filled the entry.
    """

    def __init__(self, inner: LegislationRepository, cache: Cache, *, ttl_seconds: float) -> None:
        """Keep each search for `ttl_seconds` (kept short: derived data should not linger)."""
        self._inner = inner
        self._cache = cache
        self._ttl = ttl_seconds

    async def search(
        self, filters: LegislationFilters, *, limit: int, offset: int = 0
    ) -> LegislationPage:
        """Serve the page from the cached match list, recording hit or miss on the wide event."""
        key = f"legislation:search:{filters.key()}"
        everything = self._cache.get(key)
        if everything is None:
            wide_event.annotate(cache="miss")
            # The Senado ignores paging, so an unbounded limit asks for every match.
            everything = await self._inner.search(filters, limit=sys.maxsize)
            self._cache.set(key, everything, ttl_seconds=self._ttl)
        else:
            wide_event.annotate(cache="hit")
        end = offset + limit
        return replace(
            everything,
            norms=everything.norms[offset:end],
            next_offset=end if end < everything.total else None,
        )

    async def find_by_urn(self, urn: Urn) -> NormRecord | None:
        """Pass lookups through: the detail is one cheap request."""
        return await self._inner.find_by_urn(urn)
