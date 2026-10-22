from juris_bridge_mcp.adapters.in_memory_ttl_cache import InMemoryTtlCache


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_miss_returns_none():
    assert InMemoryTtlCache(clock=FakeClock()).get("absent") is None


def test_returns_value_before_ttl_elapses():
    clock = FakeClock()
    cache = InMemoryTtlCache(clock=clock)
    cache.set("k", {"a": 1}, ttl_seconds=60)

    clock.now += 59

    assert cache.get("k") == {"a": 1}


def test_expires_value_at_ttl():
    clock = FakeClock()
    cache = InMemoryTtlCache(clock=clock)
    cache.set("k", "v", ttl_seconds=60)

    clock.now += 60

    assert cache.get("k") is None


def test_set_overwrites_and_refreshes_ttl():
    clock = FakeClock()
    cache = InMemoryTtlCache(clock=clock)
    cache.set("k", "old", ttl_seconds=10)
    clock.now += 9
    cache.set("k", "new", ttl_seconds=10)
    clock.now += 9

    assert cache.get("k") == "new"


def test_purges_expired_entries_that_were_never_read_again():
    clock = FakeClock()
    cache = InMemoryTtlCache(clock=clock, max_entries=2)
    cache.set("old", 1, ttl_seconds=10)
    cache.set("live", 2, ttl_seconds=100)
    clock.now += 10

    cache.set("new", 3, ttl_seconds=100)

    assert cache.get("live") == 2
    assert cache.get("new") == 3


def test_evicts_the_oldest_entry_when_full_of_live_ones():
    cache = InMemoryTtlCache(clock=FakeClock(), max_entries=2)
    cache.set("a", 1, ttl_seconds=100)
    cache.set("b", 2, ttl_seconds=100)

    cache.set("c", 3, ttl_seconds=100)

    assert cache.get("a") is None
    assert cache.get("b") == 2
    assert cache.get("c") == 3


def test_overwriting_a_key_does_not_evict_when_full():
    cache = InMemoryTtlCache(clock=FakeClock(), max_entries=2)
    cache.set("a", 1, ttl_seconds=100)
    cache.set("b", 2, ttl_seconds=100)

    cache.set("a", 9, ttl_seconds=100)

    assert cache.get("a") == 9
    assert cache.get("b") == 2
