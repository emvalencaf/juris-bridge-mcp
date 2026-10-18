from datetime import date

import pytest

from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure
from juris_bridge_mcp.domain.legislation import Norm, NormRecord, Relation, Urn

TEXT = "urn:lex:br:federal:lei:2021-04-01;14133"


def test_parses_a_searchable_type_into_its_key():
    urn = Urn.parse(f" {TEXT} ")

    assert urn == Urn(TEXT, "lei", date(2021, 4, 1), 14133)
    assert Urn.parse("urn:lex:br:federal:lei.complementar:2000-05-04;101").norm_type == (
        "lei-complementar"
    )


def test_keeps_the_raw_type_of_an_act_that_is_not_searchable():
    assert Urn.parse("urn:lex:br:federal:mensagem:2021-04-01;118").norm_type == "mensagem"


@pytest.mark.parametrize(
    "raw",
    [
        "lei 14133",
        "urn:lex:br:sao.paulo:estadual:lei:2021-04-01;1",
        "urn:lex:br:federal:lei:2021-02-31;1",
    ],
)
def test_rejects_what_is_not_a_federal_urn(raw):
    with pytest.raises(ToolFailure) as caught:
        Urn.parse(raw)

    assert caught.value.code is ErrorCode.INVALID_ARGUMENT


def test_latest_relations_are_distinct_and_newest_first():
    def relation(norm_id, day, kind="a"):
        return Relation(kind, f"n{norm_id}", date(2022, 1, day), norm_id)

    norm = Norm(TEXT, "lei", 14133, 2021, date(2021, 4, 1), "x")
    record = NormRecord(
        norm,
        (),
        (relation("1", 3), relation("2", 9), relation("1", 3), relation("1", 3, kind="b")),
        {},
    )

    assert [(r.norm_id, r.kind) for r in record.latest_relations()] == [
        ("2", "a"),
        ("1", "a"),
        ("1", "b"),
    ]
