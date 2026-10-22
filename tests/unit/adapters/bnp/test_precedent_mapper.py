from datetime import date

import pytest

from juris_bridge_mcp.adapters.bnp.precedent_mapper import (
    map_decisions,
    map_precedent,
    plain_text,
)
from juris_bridge_mcp.adapters.schema_drift import SchemaDrift

ITEM = {"id": "stf-rg-1", "orgao": "STF", "tipo": "RG", "nr": 1}


def test_plain_text_strips_markup_and_keeps_line_breaks():
    text = plain_text("Primeira&nbsp;linha  com  <b>negrito</b>.<br>Segunda &amp; última<BR/>")

    assert text == "Primeira linha com negrito.\nSegunda & última"


@pytest.mark.parametrize("value", ["15/10/2026", "2026-10-15", "2026-10-15T00:00:00.000-03:00"])
def test_a_date_is_read_in_either_format_the_bnp_uses(value):
    precedent = map_precedent(
        {
            **ITEM,
            "ultimaAtualizacao": value,
            "suspensoes": [{"dataSuspensao": value}],
            "historico": [{"situacao": "x", "dataAdmissao": value}],
        }
    )

    assert precedent.updated_on == date(2026, 10, 15)
    assert precedent.suspensions[0].started_on == date(2026, 10, 15)
    assert precedent.status_history[0].admitted_on == date(2026, 10, 15)


def test_an_unreadable_date_is_unknown_not_an_error():
    assert map_precedent({**ITEM, "ultimaAtualizacao": "ontem"}).updated_on is None


def test_matched_terms_come_from_every_highlight_without_repeats():
    item = {
        **ITEM,
        "highlight": {
            "tese": "a <mark>Defensoria</mark> e a <mark>defensoria</mark> <mark>Pública</mark>",
            "questao": "<mark>honorários</mark>",
        },
    }

    assert map_precedent(item).matched_terms == ("defensoria", "pública", "honorários")


def test_a_number_given_as_text_or_int_is_one_text():
    assert map_precedent({**ITEM, "nr": 11}).number == "11"
    assert map_precedent({**ITEM, "nr": "11"}).number == "11"


def test_a_leading_case_without_a_number_is_dropped():
    item = {**ITEM, "processosParadigma": [{"classe": 1}, {"numero": " 1140005 "}]}

    assert [c.raw_number for c in map_precedent(item).leading_cases] == ["1140005"]


def test_a_result_without_an_identity_is_drift():
    with pytest.raises(SchemaDrift):
        map_precedent({"orgao": "STF"})


def test_decision_texts_accept_text_or_an_object_and_refuse_other_shapes():
    assert map_decisions({"textos": ["<p>a</p>", {"texto": "b"}]}).texts == ("a", "b")
    with pytest.raises(SchemaDrift):
        map_decisions({"textos": [42]})
