import json

from tests.integration.mcp.conftest import FakeBnp


async def _call(client, **arguments):
    result = await client.call_tool("search_precedents", arguments, raise_on_error=False)
    if result.is_error:
        return json.loads(result.content[0].text)
    return result.data


async def test_returns_a_normalized_page_of_precedents(bnp: FakeBnp, mcp_client):
    page = await _call(mcp_client, court="stf", kind="RG", number="1002")

    assert page["source"] == "bnp" and page["content_kind"] == "metadata"
    assert "retrieved_at" in page and page["total"] == 1 and page["total_is_capped"] is False
    assert page["next_cursor"] is None
    item = page["items"][0]
    assert item["id"] == "stf-rg-1002"
    assert (item["court"], item["body"], item["kind"], item["number"]) == (
        "stf",
        "STF",
        "RG",
        "1002",
    )
    assert item["status"] == "Há repercussão geral. Leading case: transitado em julgado"
    assert item["question"].startswith("Discussão relativa ao pagamento de honorários")
    assert item["thesis"].startswith("1. É devido o pagamento de honorários sucumbenciais")
    assert item["updated_on"] == "2026-10-15"
    assert item["content_kind"] == "metadata"
    assert item["citation"]["text"] == "STF RG 1002" and item["citation"]["url"] is None


async def test_sends_the_filters_the_way_the_bnp_reads_them(bnp: FakeBnp, mcp_client):
    await _call(
        mcp_client,
        query="honorários +defensoria",
        court="trf1",
        kind="rg",
        number="1002",
        updated_from="2026-10-01",
        updated_to="2026-10-31",
        include_cancelled=True,
        limit=5,
    )

    assert bnp.filters == {
        "buscaGeral": "honorários +defensoria",
        "orgaos": ["TRF01"],
        "tipos": ["RG"],
        "nr": 1002,
        "atualizacaoDesde": "01/10/2026",
        "atualizacaoAte": "31/10/2026",
        "cancelados": True,
        "ordenacao": "Text",
        "pagina": 1,
        "tamanhoPagina": 5,
    }


async def test_asks_for_every_body_and_kind_when_none_is_given(bnp: FakeBnp, mcp_client):
    await _call(mcp_client, query="honorários")

    assert "STF" in bnp.filters["orgaos"] and "TNU" in bnp.filters["orgaos"]
    assert len(bnp.filters["orgaos"]) == 93
    assert "RG" in bnp.filters["tipos"] and "buscaGeral" in bnp.filters
    assert bnp.filters["cancelados"] is False and "nr" not in bnp.filters


async def test_returns_the_terms_the_bnp_highlighted_as_plain_text(bnp: FakeBnp, mcp_client):
    bnp.search_body = bnp.fixture("stj_rr_tributario.json")

    page = await _call(mcp_client, query="tributário", court="stj", kind="RR")

    item = page["items"][0]
    assert item["id"] == "stj-rr-490" and item["court"] == "stj"
    assert item["matched_terms"] == ["tributário"]
    assert "<" not in item["thesis"] and "score" not in item
    assert page["total"] == 77


async def test_an_empty_result_is_an_empty_page(bnp: FakeBnp, mcp_client):
    bnp.search_body = bnp.fixture("empty.json")

    page = await _call(mcp_client, query="zzqxjwv")

    assert page["items"] == [] and page["total"] == 0 and page["next_cursor"] is None


async def test_a_body_without_a_court_alias_has_a_null_court(bnp: FakeBnp, mcp_client):
    body = bnp.fixture("stf_rg_1002.json")
    body["resultados"][0].update(orgao="TNU", id="tnu-rg-1002")
    bnp.search_body = body

    page = await _call(mcp_client, query="x")

    assert page["items"][0]["court"] is None and page["items"][0]["body"] == "TNU"


async def test_a_capped_total_is_flagged_and_hinted(bnp: FakeBnp, mcp_client):
    bnp.search_body = bnp.fixture("capped.json")

    page = await _call(mcp_client, limit=2)

    assert page["total"] == 10000 and page["total_is_capped"] is True
    assert "narrow" in page["hint"]


async def test_a_cursor_reads_the_next_page_with_the_same_filters(bnp: FakeBnp, mcp_client):
    bnp.search_body = bnp.fixture("stj_rr_tributario.json")

    first = await _call(mcp_client, query="tributário", limit=2)
    await _call(mcp_client, query="tributário", limit=2, cursor=first["next_cursor"])

    assert first["next_cursor"] is not None
    assert bnp.filters["pagina"] == 2 and bnp.filters["tamanhoPagina"] == 2


async def test_a_capped_search_still_offers_the_next_page(bnp: FakeBnp, mcp_client):
    bnp.search_body = bnp.fixture("capped.json")

    page = await _call(mcp_client, limit=50)

    assert page["next_cursor"] is not None


async def test_a_repeated_search_is_served_from_the_cache(bnp: FakeBnp, mcp_client):
    await _call(mcp_client, court="stf", kind="RG", number="1002")
    await _call(mcp_client, court="stf", kind="RG", number="1002")

    assert len(bnp.requests) == 1


async def test_rejects_arguments_the_server_can_tell_are_wrong(bnp: FakeBnp, mcp_client):
    for arguments in ({"court": "tnu"}, {"kind": "xyz"}, {"limit": 51}, {"cursor": "nope"}):
        error = await _call(mcp_client, **arguments)
        assert error["code"] == "invalid_argument"

    assert bnp.requests == []


async def test_maps_the_sources_failures_to_error_codes(bnp: FakeBnp, mcp_client):
    cases = [
        (500, "<html>boom</html>", "source_unavailable", True),
        (403, "forbidden", "source_blocked", False),
        (400, "bad", "source_changed", False),
        (200, "<html>not json</html>", "source_changed", False),
    ]
    for status, body, code, retryable in cases:
        bnp.search_status, bnp.search_body = status, body
        error = await _call(mcp_client, query=f"x{status}")
        assert (error["code"], error["retryable"], error["source"]) == (code, retryable, "bnp")


async def test_an_answer_in_an_unknown_shape_is_source_changed(bnp: FakeBnp, mcp_client):
    bnp.search_body = {"total": 1, "resultados": {"not": "a list"}}

    error = await _call(mcp_client, query="x")

    assert error["code"] == "source_changed"
