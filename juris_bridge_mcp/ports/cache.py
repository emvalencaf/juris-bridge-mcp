"""Port: a keyed cache with per-entry TTL, so use cases never depend on a concrete one."""

from typing import Any, Protocol


class Cache(Protocol):
    """Stores values for a limited time; a miss or an expired entry reads as `None`."""

    def get(self, key: str) -> Any | None: ...

    def set(self, key: str, value: Any, *, ttl_seconds: float) -> None: ...
