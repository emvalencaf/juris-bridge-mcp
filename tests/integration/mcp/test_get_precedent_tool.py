import json

from tests.integration.mcp.conftest import FakeBnp


async def _call(client, **arguments):
    arguments = {"id": "stf-rg-1002", **arguments}
    result = await client.call_tool("get_precedent", arguments, raise_on_error=False)
    if result.is_error:
        return json.loads(result.content[0].text)
    return result.data


async def test_returns_the_precedent_in_full(bnp: FakeBnp, mcp_client):
    precedent = await _call(mcp_client)

    assert bnp.filters["orgaos"] == ["STF"] and bnp.filters["tipos"] == ["RG"]
    assert bnp.filters["nr"] == 1002 and bnp.filters["cancelados"] is True
    assert precedent["id"] == "stf-rg-1002" and precedent["source"] == "bnp"
    assert precedent["status"] == "Há repercussão geral. Leading case: transitado em julgado"
    assert [h["status"] for h in precedent["status_history"]] == [
        "Acórdão Publicado",
        "Mérito Julgado",
        "Afetado",
    ]
    assert precedent["status_history"][0]["recorded_at"] == "2026-10-13T03:00:00Z"
    assert precedent["suspensions"] == []


async def test_an_stf_incident_number_is_not_offered_as_a_cnj_number(bnp: FakeBnp, mcp_client):
    precedent = await _call(mcp_client)

    assert precedent["leading_cases"] == [
        {
            "raw_number": "1140005",
            "cnj_number": None,
            "cnj_number_digits": None,
            "case_class": 1348,
            "url": "https://portal.stf.jus.br/processos/detalhe.asp?incidente=5487108",
        }
    ]


async def test_a_cnj_number_of_a_leading_case_is_offered_for_get_case(bnp: FakeBnp, mcp_client):
    bnp.search_body = bnp.fixture("stj_rr_tributario.json")

    precedent = await _call(mcp_client, id="stj-rr-490")

    case = precedent["leading_cases"][0]
    assert case["raw_number"] == "00244986520104040000"
    assert case["cnj_number"] == "0024498-65.2010.4.04.0000"
    assert precedent["suspensions"] == [
        {
            "active": True,
            "started_on": "2011-06-06",
            "description": "Processos em segunda instância",
        }
    ]


async def test_decisions_without_text_are_a_warning_and_stay_metadata(bnp: FakeBnp, mcp_client):
    precedent = await _call(mcp_client)

    assert precedent["decisions"] == {
        "reporter": "MIN. LUÍS ROBERTO BARROSO",
        "tracking_url": None,
        "texts": [],
    }
    assert precedent["content_kind"] == "metadata"
    assert any("no decision text" in warning for warning in precedent["warnings"])
    assert bnp.requests[-1].url.path.endswith("/precedentes/stf-rg-1002/decisoes")


async def test_a_decision_text_makes_the_content_full_text(bnp: FakeBnp, mcp_client):
    bnp.decisions_body = {"relator": "X", "textos": ["<p>Ementa do acórdão.</p>"]}

    precedent = await _call(mcp_client)

    assert precedent["decisions"]["texts"] == ["Ementa do acórdão."]
    assert precedent["content_kind"] == "full_text" and precedent["warnings"] == []


async def test_a_failing_decisions_request_does_not_hide_the_precedent(bnp: FakeBnp, mcp_client):
    bnp.decisions_status, bnp.decisions_body = 500, "boom"

    precedent = await _call(mcp_client)

    assert precedent["id"] == "stf-rg-1002" and precedent["decisions"] is None
    assert any("source_unavailable" in warning for warning in precedent["warnings"])


async def test_an_unknown_id_is_not_found(bnp: FakeBnp, mcp_client):
    bnp.search_body = bnp.fixture("empty.json")

    error = await _call(mcp_client, id="stf-rg-999999")

    assert error["code"] == "not_found" and error["source"] == "bnp"


async def test_a_result_with_another_id_is_not_taken_for_the_one_asked(bnp: FakeBnp, mcp_client):
    bnp.search_body = bnp.fixture("trt04_oj_11.json")

    error = await _call(mcp_client, id="stf-rg-1002")

    assert error["code"] == "not_found"


async def test_something_that_is_not_an_id_is_an_invalid_argument(bnp: FakeBnp, mcp_client):
    error = await _call(mcp_client, id="Tema 1002")

    assert error["code"] == "invalid_argument" and bnp.requests == []
