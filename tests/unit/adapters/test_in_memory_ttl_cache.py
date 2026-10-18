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
