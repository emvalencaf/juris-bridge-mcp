from datetime import UTC, datetime

import pytest

from juris_bridge_mcp.application.use_cases.get_case import MAX_RAW_BYTES, get_case
from juris_bridge_mcp.domain.case import Case, CaseEvent, CaseRecord
from juris_bridge_mcp.domain.cnj_number import CnjNumber
from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure

DIGITS = "00008323520184013202"
NUMBER = CnjNumber.parse(DIGITS)


class _Repository:
    def __init__(self, record):
        self.record = record
        self.asked: list[tuple[str, str]] = []

    async def find(self, number, court):
        self.asked.append((number.digits, court))
        return self.record


def _event(day: int) -> CaseEvent:
    return CaseEvent(code=day, name=f"e{day}", occurred_at=datetime(2024, 1, day, tzinfo=UTC))


def _record(**kwargs) -> CaseRecord:
    case = Case(number=NUMBER, court="trf1", events=tuple(_event(d) for d in (3, 1, 2)))
    return CaseRecord(case=case, **kwargs)


async def test_events_are_the_latest_n_in_chronological_order():
    result = await get_case(_Repository(_record()), number=DIGITS, events_limit=2)

    assert [e["code"] for e in result["events"]] == [2, 3]
    assert result["events_total"] == 3


async def test_retrieved_at_comes_from_the_record():
    moment = datetime(2024, 5, 1, 12, 30, tzinfo=UTC)

    result = await get_case(_Repository(_record(retrieved_at=moment)), number=DIGITS)

    assert result["retrieved_at"] == "2024-05-01T12:30:00Z"


@pytest.mark.parametrize("limit", [0, 101])
async def test_events_limit_out_of_range_never_reaches_the_repository(limit):
    repository = _Repository(_record())

    with pytest.raises(ToolFailure) as caught:
        await get_case(repository, number=DIGITS, events_limit=limit)

    assert caught.value.code is ErrorCode.INVALID_ARGUMENT
    assert repository.asked == []


async def test_nothing_found_is_not_found():
    with pytest.raises(ToolFailure) as caught:
        await get_case(_Repository(None), number=DIGITS)

    assert caught.value.code is ErrorCode.NOT_FOUND


async def test_explicit_court_overrides_the_derived_one():
    repository = _Repository(_record())

    await get_case(repository, number=DIGITS, court="TJSP")

    assert repository.asked == [(DIGITS, "tjsp")]


async def test_raw_is_attached_unless_over_the_cap():
    small = await get_case(_Repository(_record(raw={"a": 1})), number=DIGITS, include_raw=True)
    huge = {"blob": "x" * MAX_RAW_BYTES}
    large = await get_case(_Repository(_record(raw=huge)), number=DIGITS, include_raw=True)

    assert small["raw"] == {"unstable": True, "payload": {"a": 1}}
    assert "raw" not in large
    assert any("raw payload omitted" in w for w in large["warnings"])


async def test_several_instances_add_a_warning():
    result = await get_case(_Repository(_record(matches=2)), number=DIGITS)

    assert any("2 records" in w for w in result["warnings"])
