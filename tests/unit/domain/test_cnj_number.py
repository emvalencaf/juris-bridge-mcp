import pytest

from juris_bridge_mcp.domain.cnj_number import CnjNumber, derive_court
from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure

FORMATTED = "0000832-35.2018.4.01.3202"
DIGITS = "00008323520184013202"


def test_accepts_formatted_and_digits_forms():
    assert CnjNumber.parse(FORMATTED).digits == DIGITS
    assert CnjNumber.parse(DIGITS).formatted == FORMATTED
    assert CnjNumber.parse(f"  {FORMATTED} ").digits == DIGITS


@pytest.mark.parametrize("raw", ["", "123", DIGITS + "0", "0000832-35.2018.4.01.320x", "abc"])
def test_rejects_wrong_length_or_characters(raw):
    with pytest.raises(ToolFailure) as caught:
        CnjNumber.parse(raw)

    assert caught.value.code is ErrorCode.INVALID_ARGUMENT


def test_rejects_wrong_check_digit():
    with pytest.raises(ToolFailure) as caught:
        CnjNumber.parse("0000832-36.2018.4.01.3202")

    assert caught.value.code is ErrorCode.INVALID_ARGUMENT
    assert "check digit" in caught.value.message


def _number(j: str, tr: str) -> CnjNumber:
    """Build a valid number for the given J and TR segments."""
    body = f"0000001{2020}{j}{tr}0001"
    check = 98 - int(body + "00") % 97
    return CnjNumber.parse(f"{body[:7]}{check:02d}{body[7:]}")


@pytest.mark.parametrize(
    ("j", "tr", "alias"),
    [
        ("4", "01", "trf1"),
        ("4", "06", "trf6"),
        ("5", "15", "trt15"),
        ("6", "26", "tre-sp"),
        ("6", "07", "tre-df"),
        ("8", "26", "tjsp"),
        ("8", "07", "tjdft"),
        ("8", "27", "tjto"),
        ("9", "13", "tjmmg"),
        ("9", "21", "tjmrs"),
        ("9", "26", "tjmsp"),
        ("7", "00", "stm"),
    ],
)
def test_derives_the_court_from_j_and_tr(j, tr, alias):
    assert derive_court(_number(j, tr)) == alias


def test_stf_number_is_not_covered():
    with pytest.raises(ToolFailure) as caught:
        derive_court(_number("1", "00"))

    assert caught.value.code is ErrorCode.NOT_COVERED


@pytest.mark.parametrize(("j", "tr"), [("3", "00"), ("4", "09"), ("9", "01"), ("2", "00")])
def test_underivable_court_asks_for_an_explicit_one(j, tr):
    with pytest.raises(ToolFailure) as caught:
        derive_court(_number(j, tr))

    assert caught.value.code is ErrorCode.INVALID_ARGUMENT
    assert "court" in (caught.value.hint or "")
