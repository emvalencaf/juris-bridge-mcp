import pytest

from juris_bridge_mcp.adapters.rate_limiter import RateLimiter
from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure


class FakeTime:
    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def clock(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def make(time: FakeTime, *, limit: int = 2, window: float = 60, max_wait: float = 5):
    return RateLimiter(
        "datajud",
        max_requests=limit,
        window_seconds=window,
        max_wait_seconds=max_wait,
        clock=time.clock,
        sleep=time.sleep,
    )


async def test_requests_under_the_limit_do_not_wait():
    time = FakeTime()
    limiter = make(time)

    await limiter.acquire()
    await limiter.acquire()

    assert time.slept == []


async def test_waits_for_a_slot_when_it_frees_within_the_max_wait():
    time = FakeTime()
    limiter = make(time, limit=2, window=10, max_wait=5)
    await limiter.acquire()
    time.now = 6
    await limiter.acquire()
    time.now = 7

    await limiter.acquire()  # first slot frees at t=10

    assert time.slept == [3]


async def test_raises_rate_limited_with_retry_after_instead_of_blocking_past_max_wait():
    time = FakeTime()
    limiter = make(time, limit=1, window=60, max_wait=5)
    await limiter.acquire()
    time.now = 10

    with pytest.raises(ToolFailure) as caught:
        await limiter.acquire()

    failure = caught.value
    assert failure.code is ErrorCode.RATE_LIMITED
    assert failure.source == "datajud"
    assert failure.retryable is True
    assert failure.retry_after_seconds == 50
    assert time.slept == []


async def test_a_rejected_call_does_not_consume_a_slot():
    time = FakeTime()
    limiter = make(time, limit=1, window=60, max_wait=5)
    await limiter.acquire()
    with pytest.raises(ToolFailure):
        await limiter.acquire()

    time.now = 60

    await limiter.acquire()
    assert time.slept == []


async def test_limits_are_per_instance():
    time = FakeTime()
    first, second = make(time, limit=1), make(time, limit=1)

    await first.acquire()
    await second.acquire()

    assert time.slept == []


async def test_concurrent_waiters_get_distinct_slots():
    import asyncio

    time = FakeTime()
    limiter = make(time, limit=1, window=2, max_wait=5)
    await limiter.acquire()

    await asyncio.gather(limiter.acquire(), limiter.acquire())

    assert time.now == 4
