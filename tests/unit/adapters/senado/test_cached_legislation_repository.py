from datetime import UTC, date, datetime

from juris_bridge_mcp.adapters.in_memory_ttl_cache import InMemoryTtlCache
from juris_bridge_mcp.adapters.senado.cached_legislation_repository import (
    CachedLegislationRepository,
)
from juris_bridge_mcp.domain.legislation import LegislationFilters, LegislationPage, Norm


def _norm(number: int) -> Norm:
    return Norm(
        urn=f"urn:lex:br:federal:lei:2021-01-01;{number}",
        norm_type="lei",
        number=number,
        year=2021,
        signed_on=date(2021, 1, 1),
        name=f"Lei {number}",
    )


class _Repository:
    def __init__(self, count: int = 5):
        self.norms = tuple(_norm(n) for n in range(1, count + 1))
        self.calls = 0
        self.urn_calls = 0

    async def search(self, filters, *, limit, offset=0):
        self.calls += 1
        end = offset + limit
        return LegislationPage(
            norms=self.norms[offset:end],
            total=len(self.norms),
            next_offset=end if end < len(self.norms) else None,
            retrieved_at=datetime.now(UTC),
        )

    async def find_by_urn(self, urn):
        self.urn_calls += 1
        return None


FILTERS = LegislationFilters(norm_type="lei", year=2021)


async def test_two_pages_of_one_search_make_one_upstream_request():
    inner = _Repository()
    repository = CachedLegislationRepository(inner, InMemoryTtlCache(), ttl_seconds=60)

    first = await repository.search(FILTERS, limit=2)
    second = await repository.search(FILTERS, limit=2, offset=2)

    assert inner.calls == 1
    assert [n.number for n in first.norms] == [1, 2]
    assert first.next_offset == 2
    assert [n.number for n in second.norms] == [3, 4]
    assert second.total == 5


async def test_the_last_page_has_no_next_offset():
    repository = CachedLegislationRepository(_Repository(), InMemoryTtlCache(), ttl_seconds=60)

    last = await repository.search(FILTERS, limit=2, offset=4)

    assert [n.number for n in last.norms] == [5]
    assert last.next_offset is None


async def test_a_different_filter_set_is_not_served_from_another_entry():
    inner = _Repository()
    repository = CachedLegislationRepository(inner, InMemoryTtlCache(), ttl_seconds=60)

    await repository.search(FILTERS, limit=2)
    await repository.search(LegislationFilters(norm_type="lei", year=2020), limit=2)
    await repository.search(LegislationFilters(norm_type="decreto", year=2021), limit=2)

    assert inner.calls == 3


async def test_retrieved_at_reports_when_the_source_was_asked():
    inner = _Repository()
    repository = CachedLegislationRepository(inner, InMemoryTtlCache(), ttl_seconds=60)

    first = await repository.search(FILTERS, limit=2)
    second = await repository.search(FILTERS, limit=2, offset=2)

    assert second.retrieved_at == first.retrieved_at


async def test_an_expired_entry_is_fetched_again():
    now = [0.0]
    inner = _Repository()
    repository = CachedLegislationRepository(
        inner, InMemoryTtlCache(clock=lambda: now[0]), ttl_seconds=10
    )

    await repository.search(FILTERS, limit=2)
    now[0] = 11
    await repository.search(FILTERS, limit=2)

    assert inner.calls == 2


async def test_lookups_by_urn_pass_through():
    inner = _Repository()
    repository = CachedLegislationRepository(inner, InMemoryTtlCache(), ttl_seconds=60)

    await repository.find_by_urn(object())

    assert inner.urn_calls == 1
