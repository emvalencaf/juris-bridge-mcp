"""The one HTTP client every upstream call goes through: honest identity, rate limit, retries."""

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure, rate_limited
from juris_bridge_mcp.ports.limiter import Limiter

USER_AGENT = (
    "Mozilla/5.0 (compatible; juris-bridge-mcp/0.1; "
    "+https://github.com/emvalencaf/juris-bridge-mcp)"
)

_RETRYABLE_STATUSES = frozenset({429, 503})
_BACKOFF_BASE_SECONDS = 0.5


def build_http_client(
    *, timeout_seconds: float, transport: httpx.AsyncBaseTransport | None = None
) -> httpx.AsyncClient:
    """Build a client that identifies itself honestly and never waits past the timeout."""
    return httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        timeout=timeout_seconds,
        transport=transport,
    )


class UpstreamClient:
    """Sends requests for one Source: takes a limiter slot per attempt, retries 429/503."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        source: str,
        limiter: Limiter,
        max_retries: int,
        max_wait_seconds: float,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        jitter: Callable[[], float] = lambda: random.uniform(0.5, 1.0),  # noqa: S311
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Wrap `client` for one Source; `max_retries` and `max_wait_seconds` come from settings."""
        self._client = client
        self._source = source
        self._limiter = limiter
        self._max_retries = max_retries
        self._max_wait = max_wait_seconds
        self._sleep = sleep
        self._jitter = jitter
        self._clock = clock

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Return the response; waits at most `max_wait_seconds` in total, then raise a failure."""
        waited = 0.0
        for attempt in range(self._max_retries + 1):
            started = self._clock()
            await self._limiter.acquire()
            waited += self._clock() - started
            response = await self._client.request(method, url, **kwargs)
            if response.status_code not in _RETRYABLE_STATUSES:
                return response
            retry_after = _retry_after_seconds(response)
            backoff = _BACKOFF_BASE_SECONDS * 2**attempt * self._jitter()
            wait = retry_after if retry_after is not None else backoff
            if attempt == self._max_retries or waited + wait > self._max_wait:
                raise self._failure(response, retry_after)
            await self._sleep(wait)
            waited += wait
        raise AssertionError("unreachable")  # pragma: no cover

    def _failure(self, response: httpx.Response, retry_after: float | None) -> ToolFailure:
        if response.status_code == 429:
            return rate_limited(
                self._source,
                f"{self._source} is rate limiting this server",
                retry_after_seconds=self._max_wait if retry_after is None else retry_after,
            )
        return ToolFailure(
            ErrorCode.SOURCE_UNAVAILABLE,
            f"{self._source} is unavailable (HTTP {response.status_code})",
            source=self._source,
            retryable=True,
        )


def _retry_after_seconds(response: httpx.Response) -> float | None:
    value = response.headers.get("Retry-After")
    if value is None or not value.isdigit():
        return None
    return float(value)
