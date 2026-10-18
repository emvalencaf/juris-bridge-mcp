import json

import pytest

FORMATTED = "0000832-35.2018.4.01.3202"
DIGITS = "00008323520184013202"


async def _call(client, **arguments):
    result = await client.call_tool("get_case", arguments, raise_on_error=False)
    if result.is_error:
        return json.loads(result.content[0].text)
    return result.data


async def test_returns_the_normalized_case(mcp_client):
    case = await _call(mcp_client, number=FORMATTED)

    assert case["source"] == "datajud"
    assert case["content_kind"] == "metadata"
    assert case["citation"] == {"text": f"DataJud · TRF1 · {FORMATTED}", "url": None}
    assert case["retrieved_at"].endswith("Z")
    assert case["number"] == FORMATTED
    assert case["number_digits"] == DIGITS
    assert case["court"] == "trf1"
    assert case["instance"] == "JE"
    assert case["filed_on"] == "2018-10-29"
    assert case["class"] == {"code": 436, "name": "Procedimento do Juizado Especial Cível"}
    assert case["subjects"] == [{"code": 6177, "name": "Concessão"}]
    assert case["judging_body"] == {"code": 16403, "name": "Tefé"}
    assert case["secrecy_level"] == 0
    assert case["source_system"] == {"code": 1, "name": "PJe"}
    assert case["last_updated_at"] == "2026-06-08T14:55:23.378000Z"
    assert case["warnings"] == []
    assert "raw" not in case
    assert not {"parties", "judges"} & set(case)


async def test_accepts_the_twenty_digit_form_and_queries_the_derived_court(mcp_client, datajud):
    case = await _call(mcp_client, number=DIGITS)

    assert case["number"] == FORMATTED
    assert datajud.requests[0].url.path == "/api_publica_trf1/_search"
    assert datajud.requests[0].headers["Authorization"] == "APIKey test-key"


async def test_events_default_to_the_twenty_most_recent_in_order(mcp_client, datajud):
    all_events = datajud.body["hits"]["hits"][0]["_source"]["movimentos"]
    events = await _call(mcp_client, number=FORMATTED)

    assert events["events_total"] == 43
    assert len(events["events"]) == 20
    dates = [e["occurred_at"] for e in events["events"]]
    assert dates == sorted(dates)
    assert dates[-1] == max(m["dataHora"] for m in all_events).replace(".000Z", "Z")
    assert events["events"][0].keys() == {
        "code",
        "name",
        "occurred_at",
        "judging_body",
        "complements",
    }


async def test_events_limit_is_honoured(mcp_client):
    case = await _call(mcp_client, number=FORMATTED, events_limit=3)

    assert len(case["events"]) == 3
    assert case["events_total"] == 43


@pytest.mark.parametrize("limit", [0, -1, 101])
async def test_events_limit_out_of_range_is_invalid_and_makes_no_call(mcp_client, datajud, limit):
    error = await _call(mcp_client, number=FORMATTED, events_limit=limit)

    assert error["code"] == "invalid_argument"
    assert datajud.requests == []


@pytest.mark.parametrize("number", ["0000832-36.2018.4.01.3202", "123", "abc"])
async def test_bad_number_is_invalid_and_makes_no_call(mcp_client, datajud, number):
    error = await _call(mcp_client, number=number)

    assert error["code"] == "invalid_argument"
    assert datajud.requests == []


async def test_court_argument_overrides_the_derived_one(mcp_client, datajud):
    case = await _call(mcp_client, number=FORMATTED, court="TRE-DFT")

    assert case["court"] == "tre-df"
    assert case["citation"]["text"] == f"DataJud · TRE-DF · {FORMATTED}"
    assert datajud.requests[0].url.path == "/api_publica_tre-df/_search"


async def test_unknown_court_argument_is_invalid_with_valid_aliases(mcp_client, datajud):
    error = await _call(mcp_client, number=FORMATTED, court="nope")

    assert error["code"] == "invalid_argument"
    assert "tjsp" in error["hint"]
    assert datajud.requests == []


async def test_stf_is_not_covered_and_makes_no_call(mcp_client, datajud):
    from_court = await _call(mcp_client, number=FORMATTED, court="stf")
    stf_number = "0000001-92.2020.1.00.0001"
    from_number = await _call(mcp_client, number=stf_number)

    assert from_court["code"] == from_number["code"] == "not_covered"
    assert "STF" in from_number["message"]
    assert datajud.requests == []


async def test_nothing_found_is_not_found(mcp_client, datajud):
    datajud.body = datajud.fixture("trf1_empty.json")

    error = await _call(mcp_client, number=FORMATTED)

    assert error["code"] == "not_found"
    assert error["retryable"] is False


async def test_absent_scalars_are_null_and_absent_lists_empty(mcp_client, datajud):
    source = datajud.body["hits"]["hits"][0]["_source"]
    for key in ("assuntos", "movimentos", "classe", "sistema", "dataAjuizamento", "orgaoJulgador"):
        del source[key]

    case = await _call(mcp_client, number=FORMATTED)

    assert case["subjects"] == [] and case["events"] == [] and case["events_total"] == 0
    assert case["class"] is None and case["source_system"] is None
    assert case["filed_on"] is None and case["judging_body"] is None


async def test_include_raw_attaches_the_unstable_payload(mcp_client):
    case = await _call(mcp_client, number=FORMATTED, include_raw=True)

    assert case["raw"]["unstable"] is True
    assert case["raw"]["payload"]["numeroProcesso"] == DIGITS


async def test_oversized_raw_is_omitted_with_a_warning(mcp_client, datajud):
    datajud.body["hits"]["hits"][0]["_source"]["movimentos"] *= 40

    case = await _call(mcp_client, number=FORMATTED, include_raw=True)

    assert "raw" not in case
    assert any("raw" in w for w in case["warnings"])


async def test_several_instances_are_flagged(mcp_client, datajud):
    hit = datajud.body["hits"]["hits"][0]
    older = json.loads(json.dumps(hit))
    older["_source"]["dataHoraUltimaAtualizacao"] = "2020-01-01T00:00:00.000Z"
    datajud.body["hits"]["hits"].append(older)

    case = await _call(mcp_client, number=FORMATTED)

    assert any("2 records" in w for w in case["warnings"])


async def test_a_401_is_source_auth_failed(mcp_client, datajud):
    datajud.status = 401

    error = await _call(mcp_client, number=FORMATTED)

    assert error["code"] == "source_auth_failed"
    assert error["source"] == "datajud"


async def test_a_500_is_source_unavailable_and_retryable(mcp_client, datajud):
    datajud.status = 500

    error = await _call(mcp_client, number=FORMATTED)

    assert (error["code"], error["retryable"]) == ("source_unavailable", True)


async def test_a_changed_shape_is_source_changed(mcp_client, datajud):
    datajud.body["hits"]["hits"][0]["_source"]["dataAjuizamento"] = "29/10/2018"

    error = await _call(mcp_client, number=FORMATTED)

    assert error["code"] == "source_changed"


async def test_repeated_lookup_is_served_from_the_cache(mcp_client, datajud):
    await _call(mcp_client, number=FORMATTED)
    await _call(mcp_client, number=DIGITS, events_limit=5)

    assert len(datajud.requests) == 1


async def test_cached_lookup_keeps_the_original_retrieved_at(mcp_client):
    first = await _call(mcp_client, number=FORMATTED)
    second = await _call(mcp_client, number=FORMATTED)

    assert second["retrieved_at"] == first["retrieved_at"]
