"""A `PrecedentSource` that remembers answers for a while, behind the `Cache` port."""

from juris_bridge_mcp.adapters import wide_event
from juris_bridge_mcp.domain.precedent import (
    PrecedentDecisions,
    PrecedentFilters,
    PrecedentPage,
    PrecedentRecord,
)
from juris_bridge_mcp.ports.cache import Cache
from juris_bridge_mcp.ports.precedent_source import PrecedentSource


class CachedPrecedentSource:
    """Wraps a source; the BNP changes about twice a month, so answers keep for hours.

    Only found Precedents and decisions with a text are cached, so a missing, failing or empty
    answer is asked again.
    """

    def __init__(self, inner: PrecedentSource, cache: Cache, *, ttl_seconds: float) -> None:
        """Keep each answer for `ttl_seconds`."""
        self._inner = inner
        self._cache = cache
        self._ttl = ttl_seconds

    async def search(self, filters: PrecedentFilters, *, page: int, limit: int) -> PrecedentPage:
        """Serve the page from the cache when possible, recording hit or miss."""
        key = f"precedents:{filters.key()}|{page}|{limit}"
        cached = self._cache.get(key)
        if cached is not None:
            wide_event.annotate(cache="hit")
            return cached  # type: ignore[no-any-return]
        wide_event.annotate(cache="miss")
        result = await self._inner.search(filters, page=page, limit=limit)
        self._cache.set(key, result, ttl_seconds=self._ttl)
        return result

    async def find(self, precedent_id: str) -> PrecedentRecord | None:
        """Serve a found Precedent from the cache when possible."""
        key = f"precedent:{precedent_id}"
        cached = self._cache.get(key)
        if cached is not None:
            wide_event.annotate(cache="hit")
            return cached  # type: ignore[no-any-return]
        wide_event.annotate(cache="miss")
        record = await self._inner.find(precedent_id)
        if record is not None:
            self._cache.set(key, record, ttl_seconds=self._ttl)
        return record

    async def decisions(self, precedent_id: str) -> PrecedentDecisions:
        """Serve the decisions from the cache when possible."""
        key = f"precedent-decisions:{precedent_id}"
        cached = self._cache.get(key)
        if cached is not None:
            wide_event.annotate(cache="hit")
            return cached  # type: ignore[no-any-return]
        wide_event.annotate(cache="miss")
        result = await self._inner.decisions(precedent_id)
        if result.texts:
            self._cache.set(key, result, ttl_seconds=self._ttl)
        return result
