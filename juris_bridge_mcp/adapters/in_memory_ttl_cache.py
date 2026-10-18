"""In-memory TTL Cache; lives only as long as the warm environment that holds it."""

import time
from collections.abc import Callable
from typing import Any


class InMemoryTtlCache:
    """Per-instance cache: entries are not shared across Lambda environments or restarts."""

    def __init__(
        self, clock: Callable[[], float] = time.monotonic, *, max_entries: int = 1024
    ) -> None:
        """Hold at most `max_entries` live entries, dropping the oldest when full."""
        self._clock = clock
        self._max_entries = max_entries
        self._entries: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        """Return the live value for `key`, or `None` on a miss or expiry."""
        entry = self._entries.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if self._clock() >= expires_at:
            del self._entries[key]
            return None
        return value

    def set(self, key: str, value: Any, *, ttl_seconds: float) -> None:
        """Store `value` under `key` for `ttl_seconds`, replacing any earlier entry."""
        if key not in self._entries and len(self._entries) >= self._max_entries:
            self._make_room()
        self._entries[key] = (self._clock() + ttl_seconds, value)

    def _make_room(self) -> None:
        now = self._clock()
        self._entries = {k: e for k, e in self._entries.items() if e[0] > now}
        while len(self._entries) >= self._max_entries:
            del self._entries[next(iter(self._entries))]
