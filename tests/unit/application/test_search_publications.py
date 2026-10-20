from datetime import date

import pytest

from juris_bridge_mcp.application.use_cases.search_publications import search_publications
from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure
from juris_bridge_mcp.domain.publication import PublicationPage

DAY = date(2026, 10, 15)


class _Repository:
    def __init__(self, page=None):
        self.page = page or PublicationPage(publications=(), total=0)
        self.asked: list[tuple] = []

    async def search(self, court, query, date_from, date_to, *, limit):
        self.asked.append((court, query, date_from, date_to, limit))
        return self.page


async def _search(repository, **overrides):
    arguments = {"court": "tjsp", "date_from": DAY, "date_to": DAY, "query": "recurso especial"}
    return await search_publications(repository, **{**arguments, **overrides})


async def _code(repository, **overrides) -> ErrorCode:
    with pytest.raises(ToolFailure) as caught:
        await _search(repository, **overrides)
    assert repository.asked == []
    return caught.value.code


async def test_asks_the_resolved_court_with_the_trimmed_query_as_is():
    repository = _Repository()

    result = await _search(repository, court=" TJSP ", query="  recurso especial ", limit=5)

    assert repository.asked == [("tjsp", "recurso especial", DAY, DAY, 5)]
    assert result.court == "tjsp" and result.hint is None


async def test_limit_defaults_to_10():
    repository = _Repository()

    await _search(repository)

    assert repository.asked[0][4] == 10


@pytest.mark.parametrize("limit", [0, 26])
async def test_a_limit_outside_1_to_25_is_invalid(limit):
    assert await _code(_Repository(), limit=limit) is ErrorCode.INVALID_ARGUMENT


async def test_a_window_of_32_days_is_invalid_and_31_is_allowed():
    assert (
        await _code(_Repository(), date_from=date(2026, 9, 1), date_to=date(2026, 10, 2))
        is ErrorCode.INVALID_ARGUMENT
    )
    repository = _Repository()
    await _search(repository, date_from=date(2026, 9, 1), date_to=date(2026, 10, 1))
    assert len(repository.asked) == 1


async def test_a_window_that_ends_before_it_starts_is_invalid():
    assert (
        await _code(_Repository(), date_from=date(2026, 10, 16), date_to=DAY)
        is ErrorCode.INVALID_ARGUMENT
    )


@pytest.mark.parametrize("query", ["", "    ", " abc ", "abcd"])
async def test_a_trimmed_query_under_5_characters_never_reaches_the_source(query):
    assert await _code(_Repository(), query=query) is ErrorCode.INVALID_ARGUMENT


async def test_a_court_the_djen_does_not_reach_is_not_covered():
    assert await _code(_Repository(), court="stf") is ErrorCode.NOT_COVERED


async def test_a_hint_says_when_more_publications_match_than_were_returned():
    repository = _Repository(PublicationPage(publications=(), total=40, more=True))

    result = await _search(repository)

    assert result.hint and "narrow" in result.hint
