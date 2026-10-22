import pytest

from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure
from juris_bridge_mcp.domain.precedent import (
    LeadingCase,
    PrecedentFilters,
    parse_id,
    resolve_kind,
)

VALID_CNJ = "00008323520184013202"


def test_a_valid_cnj_number_becomes_a_linked_leading_case():
    case = LeadingCase.from_raw(VALID_CNJ, case_class=1)

    assert case.cnj_number is not None and case.cnj_number.digits == VALID_CNJ
    assert case.raw_number == VALID_CNJ


@pytest.mark.parametrize("raw", ["1140005", "00008323520184013203", ""])
def test_a_number_that_is_not_a_cnj_number_stays_raw(raw):
    case = LeadingCase.from_raw(raw)

    assert case.cnj_number is None and case.raw_number == raw


def test_a_kind_is_resolved_ignoring_case():
    assert resolve_kind(" irdr ") == "IRDR"


def test_an_unknown_kind_lists_the_valid_ones():
    with pytest.raises(ToolFailure) as caught:
        resolve_kind("xyz")

    assert caught.value.code is ErrorCode.INVALID_ARGUMENT
    assert "SUM" in (caught.value.hint or "")


@pytest.mark.parametrize("value", ["stf-rg-1002", " STF-RG-1002 ", "trt04-oj-11", "tre_ac-sum-1"])
def test_parses_a_precedent_id(value):
    assert parse_id(value) == value.strip().lower()


@pytest.mark.parametrize("value", ["", "stf", "stf-rg", "stf rg 1002"])
def test_rejects_something_that_is_not_an_id(value):
    with pytest.raises(ToolFailure) as caught:
        parse_id(value)

    assert caught.value.code is ErrorCode.INVALID_ARGUMENT


def test_filters_with_different_values_have_different_keys():
    assert PrecedentFilters(query="a").key() != PrecedentFilters(query="b").key()
    assert PrecedentFilters().key() != PrecedentFilters(include_cancelled=True).key()
