import pytest

from juris_bridge_mcp.application.use_cases.legislation.search_legislation import (
    search_legislation,
)
from juris_bridge_mcp.application.use_cases.search_cases import search_cases
from juris_bridge_mcp.domain.case_search import CaseFilters
from juris_bridge_mcp.domain.cursor import Cursor
from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure
from juris_bridge_mcp.domain.legislation import LegislationFilters


class _Untouched:
    async def search(self, *args, **kwargs):
        raise AssertionError("the Source must not be asked")


async def test_search_cases_rejects_a_legislation_cursor():
    token = Cursor("senado", (10,), CaseFilters().key()).encode()

    with pytest.raises(ToolFailure) as caught:
        await search_cases(_Untouched(), court="tjsp", cursor=token)

    assert caught.value.code is ErrorCode.INVALID_ARGUMENT


async def test_search_cases_rejects_a_case_cursor_with_a_malformed_position():
    token = Cursor("tjsp", (10,), CaseFilters().key()).encode()

    with pytest.raises(ToolFailure) as caught:
        await search_cases(_Untouched(), cursor=token)

    assert caught.value.code is ErrorCode.INVALID_ARGUMENT


async def test_search_legislation_rejects_a_real_case_cursor():
    token = Cursor("tjsp", (1717858523378, "TJSP_G1_1"), "").encode()

    with pytest.raises(ToolFailure) as caught:
        await search_legislation(_Untouched(), norm_type="lei", year=2021, cursor=token)

    assert caught.value.code is ErrorCode.INVALID_ARGUMENT


async def test_search_legislation_rejects_a_position_that_is_not_an_offset():
    key = LegislationFilters("lei", None, 2021).key()
    token = Cursor("senado", (1, "x"), key).encode()

    with pytest.raises(ToolFailure) as caught:
        await search_legislation(_Untouched(), norm_type="lei", year=2021, cursor=token)

    assert caught.value.code is ErrorCode.INVALID_ARGUMENT
