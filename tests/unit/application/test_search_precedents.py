from datetime import date

import pytest

from juris_bridge_mcp.application.use_cases.search_precedents import search_precedents
from juris_bridge_mcp.domain.cursor import Cursor
from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure
from juris_bridge_mcp.domain.precedent import (
    COUNT_CAP,
    Precedent,
    PrecedentFilters,
    PrecedentPage,
)

PRECEDENT = Precedent(id="stf-rg-1002", body="STF", court="stf", kind="RG", number="1002")


class _Source:
    def __init__(self, total=1, capped=False):
        self.page = PrecedentPage(precedents=(PRECEDENT,), total=total, total_is_capped=capped)
        self.asked: list[tuple] = []

    async def search(self, filters, *, page, limit):
        self.asked.append((filters, page, limit))
        return self.page


async def test_searches_with_the_resolved_filters():
    source = _Source()

    result = await search_precedents(
        source, query=" tema ", court="STF", kind="rg", number="1002", limit=5
    )

    filters, page, limit = source.asked[0]
    assert (filters.query, filters.court, filters.kind, filters.number) == (
        "tema",
        "stf",
        "RG",
        "1002",
    )
    assert (page, limit) == (1, 5)
    assert result.precedents == (PRECEDENT,) and result.next_cursor is None


async def test_a_cursor_leads_to_the_next_page_with_the_same_filters():
    source = _Source(total=25)
    first = await search_precedents(source, query="x", limit=10)

    assert first.next_cursor is not None
    await search_precedents(source, query="x", limit=10, cursor=first.next_cursor)

    assert source.asked[1][1] == 2


async def test_the_last_page_has_no_cursor():
    result = await search_precedents(_Source(total=10), limit=10)

    assert result.next_cursor is None


async def test_a_cursor_for_other_filters_or_limit_is_refused():
    source = _Source(total=25)
    first = await search_precedents(source, query="x", limit=10)

    for kwargs in ({"query": "y", "limit": 10}, {"query": "x", "limit": 20}):
        with pytest.raises(ToolFailure) as caught:
            await search_precedents(source, cursor=first.next_cursor, **kwargs)
        assert caught.value.code is ErrorCode.INVALID_ARGUMENT


async def test_no_cursor_is_issued_past_the_source_ceiling():
    source = _Source(total=COUNT_CAP, capped=True)

    result = await search_precedents(source, limit=50, cursor=None)
    assert result.next_cursor is not None
    assert result.hint is not None and "narrow" in result.hint

    last = _Source(total=COUNT_CAP, capped=True)
    page = COUNT_CAP // 50
    key = f"{PrecedentFilters().key()}|50"
    final = await search_precedents(last, limit=50, cursor=Cursor("bnp", (page,), key).encode())
    assert final.next_cursor is None
    beyond = Cursor("bnp", (page + 1,), key).encode()
    with pytest.raises(ToolFailure) as caught:
        await search_precedents(last, limit=50, cursor=beyond)
    assert caught.value.code is ErrorCode.INVALID_ARGUMENT


@pytest.mark.parametrize(
    "kwargs",
    [
        {"limit": 0},
        {"limit": 51},
        {"court": "tnu"},
        {"kind": "xyz"},
        {"updated_from": date(2026, 2, 1), "updated_to": date(2026, 1, 1)},
        {"cursor": "not-a-cursor"},
    ],
)
async def test_invalid_arguments_are_refused(kwargs):
    with pytest.raises(ToolFailure) as caught:
        await search_precedents(_Source(), **kwargs)

    assert caught.value.code is ErrorCode.INVALID_ARGUMENT
