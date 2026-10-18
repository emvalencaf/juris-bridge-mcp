"""Per-instance sliding-window rate limiter that fails fast instead of hanging the agent."""

import asyncio
import math
import time
from collections import deque
from collections.abc import Awaitable, Callable

from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure


class RateLimiter:
    """Allows `max_requests` per `window_seconds` for one Source.

    State is per instance: each warm environment counts on its own, so the real
    aggregate rate can exceed the limit when several instances run at once.
    """

    def __init__(
        self,
        source: str,
        *,
        max_requests: int,
        window_seconds: float,
        max_wait_seconds: float,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        """Limit `source` to `max_requests` per `window_seconds`; wait up to `max_wait_seconds`."""
        self._source = source
        self._max_requests = max_requests
        self._window = window_seconds
        self._max_wait = max_wait_seconds
        self._clock = clock
        self._sleep = sleep
        self._slots: deque[float] = deque()

    async def acquire(self) -> None:
        """Take a slot, sleeping up to `max_wait_seconds`; otherwise raise `rate_limited`."""
        now = self._clock()
        while self._slots and self._slots[0] + self._window <= now:
            self._slots.popleft()
        slot = now
        if len(self._slots) >= self._max_requests:
            slot = self._slots[-self._max_requests] + self._window
        wait = slot - now
        if wait > self._max_wait:
            raise ToolFailure(
                ErrorCode.RATE_LIMITED,
                f"{self._source} request limit reached on this instance",
                source=self._source,
                retryable=True,
                retry_after_seconds=math.ceil(wait),
                hint="Wait retry_after_seconds before calling again.",
            )
        self._slots.append(slot)
        if wait > 0:
            await self._sleep(wait)
