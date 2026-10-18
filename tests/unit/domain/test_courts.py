import pytest

from juris_bridge_mcp.domain.courts import DATAJUD_COURTS, resolve_court
from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure


def test_tre_dft_is_handled_as_tre_df():
    assert resolve_court("TRE-DFT") == "tre-df"
    assert "tre-dft" not in DATAJUD_COURTS


def test_normalizes_case_and_whitespace():
    assert resolve_court("  TJSP ") == "tjsp"


def test_stf_is_not_covered():
    with pytest.raises(ToolFailure) as caught:
        resolve_court("stf")

    assert caught.value.code is ErrorCode.NOT_COVERED


def test_unknown_alias_is_invalid_with_a_hint():
    with pytest.raises(ToolFailure) as caught:
        resolve_court("nope")

    assert caught.value.code is ErrorCode.INVALID_ARGUMENT
    assert "tjsp" in (caught.value.hint or "")
