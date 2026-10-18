"""A `CaseRepository` that remembers lookups for a short time, behind the `Cache` port."""

from juris_bridge_mcp.adapters import wide_event
from juris_bridge_mcp.domain.case import CaseRecord
from juris_bridge_mcp.domain.cnj_number import CnjNumber
from juris_bridge_mcp.ports.cache import Cache
from juris_bridge_mcp.ports.case_repository import CaseRepository


class CachedCaseRepository:
    """Wraps a repository; only found Cases are cached, so a missing one is asked again."""

    def __init__(self, inner: CaseRepository, cache: Cache, *, ttl_seconds: float) -> None:
        """Keep each found Case for `ttl_seconds` (kept short: DataJud terms limit storage)."""
        self._inner = inner
        self._cache = cache
        self._ttl = ttl_seconds

    async def find(self, number: CnjNumber, court: str) -> CaseRecord | None:
        """Serve from the cache when possible, recording hit or miss on the wide event."""
        key = f"case:{court}:{number.digits}"
        cached = self._cache.get(key)
        if cached is not None:
            wide_event.annotate(cache="hit")
            return cached  # type: ignore[no-any-return]
        wide_event.annotate(cache="miss")
        record = await self._inner.find(number, court)
        if record is not None:
            self._cache.set(key, record, ttl_seconds=self._ttl)
        return record
