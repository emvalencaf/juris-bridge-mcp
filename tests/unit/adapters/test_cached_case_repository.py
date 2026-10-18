from juris_bridge_mcp.adapters.cached_case_repository import CachedCaseRepository
from juris_bridge_mcp.adapters.in_memory_ttl_cache import InMemoryTtlCache
from juris_bridge_mcp.domain.case import Case, CaseRecord
from juris_bridge_mcp.domain.cnj_number import CnjNumber

NUMBER = CnjNumber.parse("00008323520184013202")


class _Repository:
    def __init__(self, record):
        self.record = record
        self.calls = 0

    async def find(self, number, court):
        self.calls += 1
        return self.record


def _record() -> CaseRecord:
    return CaseRecord(case=Case(number=NUMBER, court="trf1"))


async def test_a_found_case_is_asked_once_per_court():
    inner = _Repository(_record())
    repository = CachedCaseRepository(inner, InMemoryTtlCache(), ttl_seconds=60)

    first = await repository.find(NUMBER, "trf1")
    again = await repository.find(NUMBER, "trf1")
    await repository.find(NUMBER, "tre-df")

    assert first is again
    assert inner.calls == 2


async def test_a_missing_case_is_asked_again():
    inner = _Repository(None)
    repository = CachedCaseRepository(inner, InMemoryTtlCache(), ttl_seconds=60)

    await repository.find(NUMBER, "trf1")
    await repository.find(NUMBER, "trf1")

    assert inner.calls == 2


async def test_an_expired_entry_is_fetched_again():
    now = [0.0]
    inner = _Repository(_record())
    cache = InMemoryTtlCache(clock=lambda: now[0])
    repository = CachedCaseRepository(inner, cache, ttl_seconds=10)

    await repository.find(NUMBER, "trf1")
    now[0] = 11
    await repository.find(NUMBER, "trf1")

    assert inner.calls == 2
