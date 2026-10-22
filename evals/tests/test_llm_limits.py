"""Rate limiting and the request cap, with a fake clock so nothing waits."""

import pytest

from evals.llm import FakeClock, RateLimiter, RequestBudget, RequestCapReached


def make(rpm=2, tpm=1000):
    clock = FakeClock()
    return clock, RateLimiter(rpm, tpm, clock, clock.sleep)


def test_requests_under_both_limits_do_not_wait():
    clock, limiter = make()

    limiter.acquire(10)
    limiter.acquire(10)

    assert clock.sleeps == []


def test_the_request_past_the_per_minute_limit_waits_for_the_window():
    clock, limiter = make(rpm=2)
    limiter.acquire(1)
    limiter.acquire(1)

    limiter.acquire(1)

    assert sum(clock.sleeps) == pytest.approx(60.0, abs=0.01)


def test_the_token_limit_makes_it_wait_even_with_requests_to_spare():
    clock, limiter = make(rpm=100, tpm=1000)
    limiter.acquire(800)

    limiter.acquire(300)

    assert sum(clock.sleeps) == pytest.approx(60.0, abs=0.01)


def test_settled_real_tokens_replace_the_estimate():
    clock, limiter = make(rpm=100, tpm=1000)
    ticket = limiter.acquire(900)
    limiter.settle(ticket, 100)

    limiter.acquire(800)

    assert clock.sleeps == []


def test_a_request_bigger_than_the_token_limit_still_goes_through_alone():
    clock, limiter = make(tpm=100)

    limiter.acquire(5000)

    assert clock.sleeps == []


def test_the_budget_stops_at_the_cap():
    budget = RequestBudget(2)
    budget.take()
    budget.take()

    with pytest.raises(RequestCapReached, match="cap of 2"):
        budget.take()
    assert budget.used == 2
