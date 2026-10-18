from datetime import date

import pytest

from juris_bridge_mcp.application.use_cases.search_cases import search_cases
from juris_bridge_mcp.domain.case import Case
from juris_bridge_mcp.domain.case_search import CaseFilters, CasePage
from juris_bridge_mcp.domain.cnj_number import CnjNumber
from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure

CASE = Case(number=CnjNumber.parse("00008323520184013202"), court="tjsp")


class _Repository:
    def __init__(self, page):
        self.page = page
        self.asked: list[tuple] = []

    async def search(self, court, filters, *, limit, after=None):
        self.asked.append((court, filters, limit, after))
        return self.page


def _page(**kwargs) -> CasePage:
    return CasePage(cases=(CASE,), total=1, total_is_lower_bound=False, **kwargs)


async def test_searches_the_resolved_court_with_the_filters():
    repository = _Repository(_page())

    result = await search_cases(
        repository, court=" TJSP ", case_class=7, filed_from=date(2024, 1, 1), limit=5
    )

    court, filters, limit, after = repository.asked[0]
    assert (court, limit, after) == ("tjsp", 5, None)
    assert filters == CaseFilters(case_class=7, filed_from=date(2024, 1, 1))
    assert result.cases == (CASE,) and result.next_cursor is None and result.hint is None


async def test_next_cursor_carries_the_court_and_resumes_the_search():
    repository = _Repository(_page(next_position=(10, "id-1")))
    first = await search_cases(repository, court="tjsp", subject=3)

    await search_cases(repository, cursor=first.next_cursor, subject=3)

    assert repository.asked[1][0] == "tjsp"
    assert repository.asked[1][3] == (10, "id-1")


async def test_cursor_for_other_filters_or_court_is_invalid():
    repository = _Repository(_page(next_position=(10, "id-1")))
    first = await search_cases(repository, court="tjsp", subject=3)

    for kwargs in ({"subject": 4}, {"subject": 3, "court": "trf1"}):
        with pytest.raises(ToolFailure) as caught:
            await search_cases(repository, cursor=first.next_cursor, **kwargs)
        assert caught.value.code is ErrorCode.INVALID_ARGUMENT
    assert len(repository.asked) == 1


async def test_lower_bound_total_carries_a_narrowing_hint():
    repository = _Repository(CasePage(cases=(CASE,), total=10000, total_is_lower_bound=True))

    result = await search_cases(repository, court="tjsp")

    assert result.total_is_lower_bound and "narrow" in result.hint


@pytest.mark.parametrize(
    "kwargs",
    [
        {"court": "tjsp", "limit": 0},
        {"court": "tjsp", "limit": 51},
        {"court": "nope"},
        {},
        {"court": "tjsp", "filed_from": date(2024, 2, 1), "filed_to": date(2024, 1, 1)},
        {"cursor": "garbage"},
    ],
)
async def test_bad_arguments_are_invalid_and_ask_nothing(kwargs):
    repository = _Repository(_page())

    with pytest.raises(ToolFailure) as caught:
        await search_cases(repository, **kwargs)

    assert caught.value.code is ErrorCode.INVALID_ARGUMENT
    assert repository.asked == []


async def test_unknown_alias_hint_lists_valid_aliases():
    with pytest.raises(ToolFailure) as caught:
        await search_cases(_Repository(_page()), court="nope")

    assert "tjsp" in caught.value.hint
