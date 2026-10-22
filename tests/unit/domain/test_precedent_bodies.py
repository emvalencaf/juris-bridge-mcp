import pytest

from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure
from juris_bridge_mcp.domain.precedent_bodies import (
    body_for_court,
    court_for_body,
    resolve_precedent_court,
)


@pytest.mark.parametrize(
    ("alias", "sigla"),
    [
        ("stf", "STF"),
        ("trf1", "TRF01"),
        ("trt4", "TRT04"),
        ("trt24", "TRT24"),
        ("tjsp", "TJSP"),
        ("tjdft", "TJDF"),
        ("tre-ac", "TRE_AC"),
        ("tjmmg", "TJMMG"),
    ],
)
def test_maps_a_court_alias_to_the_bnp_sigla_and_back(alias, sigla):
    assert body_for_court(alias) == sigla
    assert court_for_body(sigla) == alias


def test_a_body_without_an_alias_has_no_court():
    assert court_for_body("TNU") is None


def test_resolves_an_alias_ignoring_case_and_spaces():
    assert resolve_precedent_court(" STF ") == "stf"


def test_an_unknown_alias_is_an_invalid_argument():
    with pytest.raises(ToolFailure) as caught:
        resolve_precedent_court("tnu")

    assert caught.value.code is ErrorCode.INVALID_ARGUMENT
