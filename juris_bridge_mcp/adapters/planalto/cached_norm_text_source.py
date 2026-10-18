"""A `NormTextSource` that remembers parsed pages for a while, behind the `Cache` port."""

from juris_bridge_mcp.adapters import wide_event
from juris_bridge_mcp.domain.legislation import Urn
from juris_bridge_mcp.domain.legislation_text import NormText
from juris_bridge_mcp.ports.cache import Cache
from juris_bridge_mcp.ports.norm_text_source import NormTextSource


class CachedNormTextSource:
    """Wraps a Source; only found texts are cached, so a missing page is asked again.

    A hit also skips the 404 probes for the consolidated page name, since the cached
    `NormText` already carries the URL that resolved.
    """

    def __init__(self, inner: NormTextSource, cache: Cache, *, ttl_seconds: float) -> None:
        """Keep each parsed text for `ttl_seconds` (norm pages change rarely)."""
        self._inner = inner
        self._cache = cache
        self._ttl = ttl_seconds

    async def fetch(self, urn: Urn) -> NormText | None:
        """Serve from the cache when possible, recording hit or miss on the wide event."""
        key = f"norm-text:{urn.text}"
        cached = self._cache.get(key)
        if cached is not None:
            wide_event.annotate(cache="hit")
            return cached  # type: ignore[no-any-return]
        wide_event.annotate(cache="miss")
        text = await self._inner.fetch(urn)
        if text is not None:
            self._cache.set(key, text, ttl_seconds=self._ttl)
        return text
