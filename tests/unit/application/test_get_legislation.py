import json
from datetime import date

import pytest

from juris_bridge_mcp.application.use_cases.get_legislation import (
    DEFAULT_RELATIONS_LIMIT,
    get_legislation,
)
from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure
from juris_bridge_mcp.domain.legislation import Norm, NormRecord, Relation

URN = "urn:lex:br:federal:lei:2021-04-01;14133"
NORM = Norm(URN, "lei", 14133, 2021, date(2021, 4, 1), "Lei nº 14.133 de 01/04/2021")


class _Repository:
    def __init__(self, record):
        self.record = record
        self.asked: list[str] = []

    async def find(self, urn):
        self.asked.append(urn)
        return self.record


def _record(relations=(), raw=None) -> NormRecord:
    return NormRecord(NORM, (), tuple(relations), raw if raw is not None else {})


def _relation(day: int, kind="Declaração de Alteração Permanente") -> Relation:
    return Relation(kind, f"Lei nº {day}", date(2022, 1, day), str(day))


async def _failure(record, **arguments) -> ToolFailure:
    with pytest.raises(ToolFailure) as caught:
        await get_legislation(_Repository(record), **arguments)
    return caught.value


async def test_fetches_the_norm_by_urn():
    repository = _Repository(_record())

    result = await get_legislation(repository, urn=f" {URN} ")

    assert repository.asked == [URN] and result.norm == NORM
    assert result.relations == () and result.relations_total == 0 and result.raw is None


async def test_keeps_the_most_recent_relations_up_to_the_limit():
    record = _record([_relation(d) for d in (3, 9, 1, 7)])

    result = await get_legislation(_Repository(record), urn=URN, relations_limit=2)

    assert [r.norm_id for r in result.relations] == ["9", "7"]
    assert result.relations_total == 4


async def test_collapses_a_norm_repeated_with_the_same_kind():
    record = _record([_relation(5), _relation(5), _relation(5, kind="Declaração de Veto Original")])

    result = await get_legislation(_Repository(record), urn=URN)

    assert result.relations_total == 2 and DEFAULT_RELATIONS_LIMIT == 25


async def test_an_unknown_urn_is_not_found():
    failure = await _failure(None, urn=URN)

    assert failure.code is ErrorCode.NOT_FOUND and failure.source == "senado"


@pytest.mark.parametrize("urn", ["lei 14133", "urn:lex:br:sao.paulo:estadual:lei:2021-04-01;1"])
async def test_a_malformed_urn_is_invalid(urn):
    failure = await _failure(_record(), urn=urn)

    assert failure.code is ErrorCode.INVALID_ARGUMENT and "search_legislation" in failure.hint


@pytest.mark.parametrize("limit", [0, 101])
async def test_relations_limit_is_bounded(limit):
    failure = await _failure(_record(), urn=URN, relations_limit=limit)

    assert failure.code is ErrorCode.INVALID_ARGUMENT


async def test_the_text_is_not_available_yet():
    failure = await _failure(_record(), urn=URN, include_text=True)

    assert failure.code is ErrorCode.NOT_COVERED


async def test_raw_is_attached_on_request_and_marked_unstable():
    result = await get_legislation(_Repository(_record(raw={"a": 1})), urn=URN, include_raw=True)

    assert result.raw == {"unstable": True, "payload": {"a": 1}}


async def test_raw_larger_than_the_cap_is_dropped_with_a_warning():
    record = _record(raw={"blob": "x" * 300_000})

    result = await get_legislation(_Repository(record), urn=URN, include_raw=True)

    assert result.raw is None and "raw payload omitted" in result.warnings[0]
    assert len(json.dumps(record.raw)) > 256 * 1024
