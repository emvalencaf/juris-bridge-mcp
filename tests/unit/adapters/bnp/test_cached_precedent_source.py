from juris_bridge_mcp.adapters.bnp.cached_precedent_source import CachedPrecedentSource
from juris_bridge_mcp.adapters.in_memory_ttl_cache import InMemoryTtlCache
from juris_bridge_mcp.domain.precedent import (
    Precedent,
    PrecedentDecisions,
    PrecedentFilters,
    PrecedentPage,
    PrecedentRecord,
)

PRECEDENT = Precedent(id="stf-rg-1", body="STF", court="stf", kind="RG", number="1")


class _Source:
    def __init__(self, record=None, decisions=None):
        self.record = record
        self._decisions = decisions or PrecedentDecisions()
        self.calls: list[str] = []

    async def search(self, filters, *, page, limit):
        self.calls.append("search")
        return PrecedentPage(precedents=(PRECEDENT,), total=1, total_is_capped=False)

    async def find(self, precedent_id):
        self.calls.append("find")
        return self.record

    async def decisions(self, precedent_id):
        self.calls.append("decisions")
        return self._decisions


def _cached(inner):
    return CachedPrecedentSource(inner, InMemoryTtlCache(), ttl_seconds=60)


async def test_a_search_is_asked_once_per_filters_page_and_limit():
    inner = _Source()
    source = _cached(inner)

    await source.search(PrecedentFilters(query="a"), page=1, limit=10)
    await source.search(PrecedentFilters(query="a"), page=1, limit=10)
    await source.search(PrecedentFilters(query="a"), page=2, limit=10)
    await source.search(PrecedentFilters(query="b"), page=1, limit=10)

    assert inner.calls == ["search"] * 3


async def test_a_found_precedent_is_kept_and_a_missing_one_is_asked_again():
    found, missing = _Source(PrecedentRecord(PRECEDENT)), _Source(None)

    for inner in (found, missing):
        source = _cached(inner)
        await source.find("stf-rg-1")
        await source.find("stf-rg-1")

    assert found.calls == ["find"] and missing.calls == ["find", "find"]


async def test_decisions_with_text_are_kept_and_empty_ones_are_asked_again():
    with_text = _Source(decisions=PrecedentDecisions(texts=("ementa",)))
    empty = _Source()

    for inner in (with_text, empty):
        source = _cached(inner)
        await source.decisions("stf-rg-1")
        await source.decisions("stf-rg-1")

    assert with_text.calls == ["decisions"] and empty.calls == ["decisions", "decisions"]


async def test_a_cached_page_keeps_the_moment_the_source_was_asked():
    source = _cached(_Source())

    first = await source.search(PrecedentFilters(), page=1, limit=10)
    second = await source.search(PrecedentFilters(), page=1, limit=10)

    assert second.retrieved_at == first.retrieved_at
