import pytest

from juris_bridge_mcp.adapters import wide_event
from juris_bridge_mcp.adapters.in_memory_ttl_cache import InMemoryTtlCache
from juris_bridge_mcp.adapters.planalto.cached_norm_text_source import CachedNormTextSource
from juris_bridge_mcp.adapters.wide_event import WideEvent
from juris_bridge_mcp.domain.errors import ErrorCode, source_failure
from juris_bridge_mcp.domain.legislation import Urn
from juris_bridge_mcp.domain.legislation_text import NormText

LEI = Urn.parse("urn:lex:br:federal:lei:2021-04-01;14133")
DECRETO = Urn.parse("urn:lex:br:federal:decreto:2020-01-01;10000")


class _Source:
    def __init__(self, text):
        self.text = text
        self.calls = 0

    async def fetch(self, urn):
        self.calls += 1
        return self.text


def _text() -> NormText:
    return NormText(text="Art. 1º Texto.", articles=(), url="https://example/l14133compilado.htm")


async def test_a_norm_text_is_fetched_once_per_urn():
    inner = _Source(_text())
    source = CachedNormTextSource(inner, InMemoryTtlCache(), ttl_seconds=60)

    first = await source.fetch(LEI)
    again = await source.fetch(LEI)
    await source.fetch(DECRETO)

    assert first is again
    assert inner.calls == 2


async def test_a_missing_page_is_asked_again():
    inner = _Source(None)
    source = CachedNormTextSource(inner, InMemoryTtlCache(), ttl_seconds=60)

    await source.fetch(LEI)
    await source.fetch(LEI)

    assert inner.calls == 2


async def test_an_expired_entry_is_fetched_again():
    now = [0.0]
    inner = _Source(_text())
    source = CachedNormTextSource(inner, InMemoryTtlCache(clock=lambda: now[0]), ttl_seconds=10)

    await source.fetch(LEI)
    now[0] = 11
    await source.fetch(LEI)

    assert inner.calls == 2


async def test_an_inner_error_propagates_and_is_not_cached():
    class _Failing:
        calls = 0

        async def fetch(self, urn):
            self.calls += 1
            raise source_failure("planalto", ErrorCode.SOURCE_UNAVAILABLE, "down", retryable=True)

    inner = _Failing()
    source = CachedNormTextSource(inner, InMemoryTtlCache(), ttl_seconds=60)

    for _ in range(2):
        with pytest.raises(Exception, match="down"):
            await source.fetch(LEI)

    assert inner.calls == 2


async def test_hit_and_miss_are_recorded_on_the_wide_event():
    event = WideEvent({}, "r")
    token = wide_event.start(event)
    try:
        source = CachedNormTextSource(_Source(_text()), InMemoryTtlCache(), ttl_seconds=60)
        await source.fetch(LEI)
        assert event.fields["cache"] == "miss"
        await source.fetch(LEI)
        assert event.fields["cache"] == "hit"
    finally:
        wide_event.stop(token)
