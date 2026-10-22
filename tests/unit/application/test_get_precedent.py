import pytest

from juris_bridge_mcp.application.use_cases.get_precedent import get_precedent
from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure, source_failure
from juris_bridge_mcp.domain.precedent import Precedent, PrecedentDecisions, PrecedentRecord

PRECEDENT = Precedent(id="stf-rg-1002", body="STF", court="stf", kind="RG", number="1002")

RECORD = PrecedentRecord(PRECEDENT)


class _Source:
    def __init__(self, record=RECORD, decisions=None, failure=None):
        self.record, self._decisions, self.failure = record, decisions, failure
        self.found: list[str] = []

    async def find(self, precedent_id):
        self.found.append(precedent_id)
        return self.record

    async def decisions(self, precedent_id):
        if self.failure:
            raise self.failure
        return self._decisions or PrecedentDecisions()


async def test_returns_the_precedent_and_its_decision_texts():
    source = _Source(decisions=PrecedentDecisions(reporter="X", texts=("ementa",)))

    result = await get_precedent(source, precedent_id=" STF-RG-1002 ")

    assert source.found == ["stf-rg-1002"]
    assert result.precedent == PRECEDENT
    assert result.decisions is not None and result.decisions.texts == ("ementa",)
    assert result.warnings == ()


async def test_empty_decisions_are_a_warning_not_an_error():
    result = await get_precedent(_Source(), precedent_id="stf-rg-1002")

    assert result.decisions == PrecedentDecisions()
    assert any("no decision text" in w for w in result.warnings)


async def test_failing_decisions_do_not_hide_the_precedent():
    failure = source_failure("bnp", ErrorCode.SOURCE_UNAVAILABLE, "down", retryable=True)

    result = await get_precedent(_Source(failure=failure), precedent_id="stf-rg-1002")

    assert result.precedent == PRECEDENT and result.decisions is None
    assert any("source_unavailable" in w for w in result.warnings)


async def test_an_unknown_id_is_not_found():
    with pytest.raises(ToolFailure) as caught:
        await get_precedent(_Source(record=None), precedent_id="stf-rg-9")

    assert caught.value.code is ErrorCode.NOT_FOUND and caught.value.source == "bnp"


async def test_something_that_is_not_an_id_is_an_invalid_argument():
    with pytest.raises(ToolFailure) as caught:
        await get_precedent(_Source(), precedent_id="Tema 1002")

    assert caught.value.code is ErrorCode.INVALID_ARGUMENT
