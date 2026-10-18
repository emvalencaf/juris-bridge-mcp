import pytest

from juris_bridge_mcp.application.use_cases.legislation.search_legislation import search_legislation
from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure
from juris_bridge_mcp.domain.legislation import LegislationFilters, LegislationPage


class _Repository:
    def __init__(self, page):
        self.page = page
        self.asked: list[tuple] = []

    async def search(self, filters, *, limit, offset=0):
        self.asked.append((filters, limit, offset))
        return self.page


def _page(**kwargs) -> LegislationPage:
    return LegislationPage(norms=(), total=0, **kwargs)


async def _invalid(**arguments) -> ToolFailure:
    with pytest.raises(ToolFailure) as caught:
        await search_legislation(_Repository(_page()), **arguments)
    assert caught.value.code is ErrorCode.INVALID_ARGUMENT
    return caught.value


async def test_searches_the_resolved_type_with_number_and_year():
    repository = _Repository(_page())

    result = await search_legislation(
        repository, norm_type=" Lei Complementar ", number=101, year=2000, limit=5
    )

    filters, limit, offset = repository.asked[0]
    assert filters == LegislationFilters("lei-complementar", 101, 2000)
    assert (limit, offset) == (5, 0)
    assert result.norms == () and result.next_cursor is None


async def test_an_unknown_type_lists_the_valid_ones():
    failure = await _invalid(norm_type="portaria", number=1)

    assert "lei-complementar" in failure.hint


@pytest.mark.parametrize(
    "arguments",
    [
        {"norm_type": "lei"},
        {"norm_type": "lei", "number": 0},
        {"norm_type": "lei", "year": 0},
        {"norm_type": "lei", "number": 1, "limit": 0},
        {"norm_type": "lei", "number": 1, "limit": 51},
    ],
)
async def test_rejects_arguments_that_cannot_locate_a_norm(arguments):
    await _invalid(**arguments)


async def test_next_cursor_resumes_at_the_next_offset():
    repository = _Repository(_page(next_offset=2))
    first = await search_legislation(repository, norm_type="lei", year=2021, limit=2)

    await search_legislation(
        repository, norm_type="lei", year=2021, limit=2, cursor=first.next_cursor
    )

    assert repository.asked[1][2] == 2


async def test_a_cursor_for_other_filters_is_rejected():
    repository = _Repository(_page(next_offset=2))
    first = await search_legislation(repository, norm_type="lei", year=2021)

    await _invalid(norm_type="lei", year=2020, cursor=first.next_cursor)


async def test_a_case_cursor_is_rejected():
    from juris_bridge_mcp.domain.cursor import Cursor

    token = Cursor("tjsp", (1, "x"), "").encode()

    await _invalid(norm_type="lei", year=2021, cursor=token)


async def test_a_cursor_with_a_non_numeric_offset_is_rejected():
    from juris_bridge_mcp.domain.cursor import Cursor

    token = Cursor("senado", ("x",), LegislationFilters("lei", None, 2021).key()).encode()

    await _invalid(norm_type="lei", year=2021, cursor=token)
