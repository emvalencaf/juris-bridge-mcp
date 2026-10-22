import pytest

from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure, not_covered, rate_limited


def test_error_codes_are_the_closed_set_of_eight():
    assert {c.value for c in ErrorCode} == {
        "invalid_argument",
        "not_found",
        "not_covered",
        "rate_limited",
        "source_unavailable",
        "source_auth_failed",
        "source_changed",
        "source_blocked",
    }


def test_payload_omits_optional_fields_when_absent():
    failure = ToolFailure(ErrorCode.NOT_FOUND, "no such case", source="datajud", retryable=False)

    assert failure.payload() == {
        "code": "not_found",
        "message": "no such case",
        "source": "datajud",
        "retryable": False,
    }


def test_payload_includes_retry_and_hint():
    failure = ToolFailure(
        ErrorCode.RATE_LIMITED,
        "slow down",
        source="datajud",
        retryable=True,
        retry_after_seconds=3,
        hint="wait",
    )

    assert failure.payload()["retry_after_seconds"] == 3
    assert failure.payload()["hint"] == "wait"


def test_unknown_code_is_rejected():
    with pytest.raises(ValueError):
        ErrorCode("boom")


def test_rate_limited_helper_rounds_the_wait_up_and_is_retryable():
    failure = rate_limited("datajud", "slow down", retry_after_seconds=1.2)

    assert failure.code is ErrorCode.RATE_LIMITED
    assert failure.source == "datajud"
    assert failure.retryable is True
    assert failure.retry_after_seconds == 2


def test_not_covered_names_the_source_and_is_not_retryable():
    failure = not_covered("djen", "STF does not publish.", "See list_coverage.")

    assert failure.payload() == {
        "code": "not_covered",
        "message": "STF does not publish.",
        "source": "djen",
        "retryable": False,
        "hint": "See list_coverage.",
    }
