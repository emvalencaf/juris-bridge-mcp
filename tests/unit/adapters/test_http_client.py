import httpx
import pytest

from juris_bridge_mcp.adapters.http_client import (
    USER_AGENT,
    UpstreamClient,
    build_http_client,
)
from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure


class Recorder:
    def __init__(self) -> None:
        self.slept: list[float] = []
        self.acquired = 0

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)

    async def acquire(self) -> None:
        self.acquired += 1


def scripted(*responses: httpx.Response):
    queue = list(responses)
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return queue.pop(0)

    return httpx.MockTransport(handler), seen


def make(transport, rec: Recorder, *, max_retries: int = 2, max_wait: float = 5):
    return UpstreamClient(
        build_http_client(timeout_seconds=7, transport=transport),
        source="datajud",
        limiter=rec,
        max_retries=max_retries,
        max_wait_seconds=max_wait,
        sleep=rec.sleep,
        jitter=lambda: 1.0,
    )


def test_user_agent_is_honest_and_mozilla_compatible():
    assert USER_AGENT.startswith("Mozilla/5.0 (compatible; juris-bridge-mcp/")
    assert "github.com/emvalencaf/juris-bridge-mcp" in USER_AGENT


async def test_factory_sets_user_agent_and_timeout():
    transport, seen = scripted(httpx.Response(200))
    client = build_http_client(timeout_seconds=7, transport=transport)

    await client.get("https://example.test/")

    assert seen[0].headers["user-agent"] == USER_AGENT
    assert client.timeout == httpx.Timeout(7)


async def test_returns_success_without_retry_and_takes_a_limiter_slot():
    transport, seen = scripted(httpx.Response(200, json={"ok": True}))
    rec = Recorder()

    response = await make(transport, rec).request("GET", "https://example.test/")

    assert response.json() == {"ok": True}
    assert len(seen) == 1
    assert rec.acquired == 1
    assert rec.slept == []


async def test_retries_503_with_exponential_backoff_then_succeeds():
    transport, seen = scripted(httpx.Response(503), httpx.Response(503), httpx.Response(200))
    rec = Recorder()

    response = await make(transport, rec).request("GET", "https://example.test/")

    assert response.status_code == 200
    assert len(seen) == 3
    assert rec.acquired == 3
    assert rec.slept == [0.5, 1.0]


async def test_jitter_scales_the_backoff():
    transport, _ = scripted(httpx.Response(429), httpx.Response(200))
    rec = Recorder()
    client = UpstreamClient(
        build_http_client(timeout_seconds=7, transport=transport),
        source="datajud",
        limiter=rec,
        max_retries=2,
        max_wait_seconds=5,
        sleep=rec.sleep,
        jitter=lambda: 0.5,
    )

    await client.request("GET", "https://example.test/")

    assert rec.slept == [0.25]


async def test_gives_up_after_two_retries_on_503_as_source_unavailable():
    transport, seen = scripted(*[httpx.Response(503)] * 3)

    with pytest.raises(ToolFailure) as caught:
        await make(transport, Recorder()).request("GET", "https://example.test/")

    assert len(seen) == 3
    assert caught.value.code is ErrorCode.SOURCE_UNAVAILABLE
    assert caught.value.retryable is True


async def test_gives_up_after_two_retries_on_429_as_rate_limited():
    transport, seen = scripted(*[httpx.Response(429)] * 3)

    with pytest.raises(ToolFailure) as caught:
        await make(transport, Recorder()).request("GET", "https://example.test/")

    assert len(seen) == 3
    assert caught.value.code is ErrorCode.RATE_LIMITED
    assert caught.value.retry_after_seconds is not None


async def test_honors_a_short_retry_after_header():
    transport, _ = scripted(httpx.Response(429, headers={"Retry-After": "2"}), httpx.Response(200))
    rec = Recorder()

    await make(transport, rec).request("GET", "https://example.test/")

    assert rec.slept == [2.0]


async def test_long_retry_after_returns_rate_limited_immediately():
    transport, seen = scripted(httpx.Response(429, headers={"Retry-After": "120"}))
    rec = Recorder()

    with pytest.raises(ToolFailure) as caught:
        await make(transport, rec).request("GET", "https://example.test/")

    assert caught.value.code is ErrorCode.RATE_LIMITED
    assert caught.value.retry_after_seconds == 120
    assert len(seen) == 1
    assert rec.slept == []


async def test_other_statuses_are_returned_untouched():
    transport, seen = scripted(httpx.Response(404))

    response = await make(transport, Recorder()).request("GET", "https://example.test/")

    assert response.status_code == 404
    assert len(seen) == 1
