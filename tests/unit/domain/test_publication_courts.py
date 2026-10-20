from datetime import date

import pytest

from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure
from juris_bridge_mcp.domain.publication_courts import resolve_djen_court


def test_resolves_an_alias_ignoring_case_and_spaces():
    assert resolve_djen_court(" TJSP ", date(2026, 10, 15)) == "tjsp"


@pytest.mark.parametrize("alias", ["stf", "tre-sp", "tre-df"])
def test_a_court_that_is_not_a_djen_sender_is_not_covered(alias):
    with pytest.raises(ToolFailure) as caught:
        resolve_djen_court(alias, date(2026, 10, 15))

    assert caught.value.code is ErrorCode.NOT_COVERED
    assert caught.value.source == "djen"


def test_a_window_ending_before_the_court_start_is_not_covered():
    with pytest.raises(ToolFailure) as caught:
        resolve_djen_court("tjsp", date(2024, 1, 31))

    assert caught.value.code is ErrorCode.NOT_COVERED


def test_a_window_reaching_the_court_start_is_allowed():
    assert resolve_djen_court("stj", date(2024, 12, 31)) == "stj"


def test_an_unknown_alias_is_invalid():
    with pytest.raises(ToolFailure) as caught:
        resolve_djen_court("xyz", date(2026, 10, 15))

    assert caught.value.code is ErrorCode.INVALID_ARGUMENT
