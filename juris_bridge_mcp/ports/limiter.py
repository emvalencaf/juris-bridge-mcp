"""Port: gate that keeps outbound calls inside a Source's request limit."""

from typing import Protocol


class Limiter(Protocol):
    """Hands out request slots for one Source."""

    async def acquire(self) -> None:
        """Wait briefly for a slot, or raise a `rate_limited` failure instead of hanging."""
        ...
