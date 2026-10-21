import asyncio
import json

import pytest

from tests.integration.mcp.conftest import FakeDjen


@pytest.fixture
def fast_sleep(monkeypatch):
    async def no_sleep(seconds):
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)


async def _call(client, **arguments):
    arguments = {
        "court": "tjsp",
        "date_from": "2026-10-15",
        "date_to": "2026-10-15",
        "query": "recurso especial",
        **arguments,
    }
    result = await client.call_tool("search_publications", arguments, raise_on_error=False)
    if result.is_error:
        return json.loads(result.content[0].text)
    return result.data


async def test_returns_a_normalized_page_of_publications(djen: FakeDjen, mcp_client):
    page = await _call(mcp_client)

    assert page["source"] == "djen" and page["content_kind"] == "metadata"
    assert page["court"] == "tjsp" and "retrieved_at" in page
    first = page["items"][0]
    assert first["cnj_number"] == "1234567-76.2025.8.26.0100"
    assert first["cnj_number_digits"] == "12345677620258260100"
    assert first["document_type"] == "DESPACHO/DECISÃO"
    assert first["kind"] == "decisao_interlocutoria"
    assert "heuristic" in page["kind_classification"]
    assert page["not_decisions_dropped"] == 0
    assert first["published_on"] == "2026-10-15"
    assert first["excerpt"].startswith("DECISÃO Vistos.")
    assert first["text_length"] > 0
    assert isinstance(first["score"], float) and isinstance(first["matched_terms"], list)
    assert first["content_kind"] == "metadata" and first["source"] == "djen"
    assert first["citation"] == {
        "text": "TJSP, DESPACHO/DECISÃO, proc. 1234567-76.2025.8.26.0100, "
        "publicada em 15/10/2026 (DJEN)",
        "url": "https://dje.example.test/publicacao/900000001",
    }
    assert page["items"][1]["citation"]["url"] is None
    assert len({item["id"] for item in page["items"]}) == 2


async def test_the_tool_description_warns_about_personal_data(mcp_client):
    tool = next(t for t in await mcp_client.list_tools() if t.name == "search_publications")

    assert "LGPD" in tool.description and "personal data" in tool.description


async def test_an_invalid_argument_never_calls_the_djen(djen: FakeDjen, mcp_client):
    error = await _call(mcp_client, query="abc")

    assert error["code"] == "invalid_argument" and djen.requests == []


async def test_a_court_the_djen_does_not_reach_is_not_covered(djen: FakeDjen, mcp_client):
    error = await _call(mcp_client, court="stf")

    assert error["code"] == "not_covered" and djen.requests == []


async def test_a_djen_failure_carries_its_error_code(fast_sleep, djen: FakeDjen, mcp_client):
    djen.status = 429

    error = await _call(mcp_client)

    assert error["code"] == "rate_limited" and error["retry_after_seconds"] == 60
    assert len(djen.requests) == 2


async def test_the_kind_filter_keeps_only_that_kind(djen: FakeDjen, mcp_client):
    page = await _call(mcp_client, kind="acordao")

    assert [item["kind"] for item in page["items"]] == ["acordao"]


async def test_an_unknown_kind_never_calls_the_djen(djen: FakeDjen, mcp_client):
    error = await _call(mcp_client, kind="despacho")

    assert error["code"] == "invalid_argument" and djen.requests == []


async def test_a_search_over_a_quiet_window_is_complete_after_walking_every_day(
    djen: FakeDjen, mcp_client
):
    djen.body = FakeDjen.fixture("empty.json")

    page = await _call(mcp_client, date_from="2026-10-13", date_to="2026-10-15")

    assert page["complete"] is True and page["incomplete_reason"] is None
    assert page["next_cursor"] is None
    days = [r.url.params["dataDisponibilizacaoInicio"] for r in djen.requests]
    assert days == ["2026-10-15", "2026-10-14", "2026-10-13"]


async def test_a_long_quiet_window_stops_at_the_budget_with_a_cursor(djen: FakeDjen, mcp_client):
    djen.body = FakeDjen.fixture("empty.json")
    window = {"date_from": "2026-09-16", "date_to": "2026-10-15"}

    first = await _call(mcp_client, **window)

    assert len(djen.requests) == 10
    assert first["complete"] is False and first["incomplete_reason"] == "budget"
    assert first["next_cursor"] and "hint" in first


async def test_a_foreign_cursor_is_invalid_argument(djen: FakeDjen, mcp_client):
    error = await _call(mcp_client, cursor="bm90IGEgY3Vyc29y")

    assert error["code"] == "invalid_argument" and djen.requests == []


async def test_a_day_at_the_count_cap_is_split_by_orgao_and_reported_as_slice_cap(
    djen: FakeDjen, mcp_client
):
    capped = FakeDjen.fixture("tjsp_decisions.json")
    capped["count"] = 10000
    normal = FakeDjen.fixture("tjsp_decisions.json")
    djen.responder = lambda request: normal if "orgaoId" in request.url.params else capped

    page = await _call(mcp_client)

    asked = [r.url.params.get("orgaoId") for r in djen.requests]
    assert asked == [None, "1001", "1002"]
    assert page["complete"] is False and page["incomplete_reason"] == "slice_cap"
    assert page["next_cursor"] is None and "hint" in page
    assert len(page["items"]) == 4


async def test_the_tool_description_says_the_score_is_page_relative(mcp_client):
    tool = next(t for t in await mcp_client.list_tools() if t.name == "search_publications")

    description = " ".join(tool.description.split())
    assert "not comparable across pages" in description
    assert "no global relevance ordering" in description


async def test_a_cnj_number_lists_the_publications_of_the_case(djen: FakeDjen, mcp_client):
    page = await _call(mcp_client, court=None, query=None, cnj_number="1234567-76.2025.8.26.0100")

    params = djen.requests[0].url.params
    assert params["numeroProcesso"] == "12345677620258260100" and "texto" not in params
    assert params["siglaTribunal"] == "TJSP" and page["court"] == "tjsp"
    assert page["items"][0]["cnj_number"] == "1234567-76.2025.8.26.0100"
    assert page["items"][0]["cnj_number_digits"] == "12345677620258260100"


async def test_an_invalid_cnj_number_never_calls_the_djen(djen: FakeDjen, mcp_client):
    error = await _call(mcp_client, court=None, query=None, cnj_number="1234567-76.2025.8.26.0101")

    assert error["code"] == "invalid_argument" and djen.requests == []


async def test_a_cnj_number_with_no_publications_is_an_empty_page(djen: FakeDjen, mcp_client):
    djen.body = FakeDjen.fixture("empty.json")

    page = await _call(mcp_client, court=None, query=None, cnj_number="1234567-76.2025.8.26.0100")

    assert page["items"] == [] and page["complete"] is True


async def test_a_cnj_number_documents_itself_in_the_tool_description(mcp_client):
    tool = next(t for t in await mcp_client.list_tools() if t.name == "search_publications")

    assert "cnj_number" in tool.description


async def _id_of(client, index: int) -> str:
    page = await _call(client)
    return page["items"][index]["id"]


async def test_get_publication_returns_the_plain_text_of_a_plain_item(djen: FakeDjen, mcp_client):
    publication_id = await _id_of(mcp_client, 0)

    result = await mcp_client.call_tool("get_publication", {"id": publication_id})

    full = result.data
    assert full["content_kind"] == "full_text" and full["source"] == "djen"
    assert full["text"].startswith("DECISÃO Vistos.") and full["truncated"] is False
    assert full["text_length"] == len(full["text"]) and full["next_cursor"] is None
    assert full["citation"]["text"].startswith("TJSP, DESPACHO/DECISÃO")
    assert full["id"] == publication_id


async def test_get_publication_strips_the_html_of_an_html_item(djen: FakeDjen, mcp_client):
    publication_id = await _id_of(mcp_client, 1)

    result = await mcp_client.call_tool("get_publication", {"id": publication_id})

    assert "<" not in result.data["text"] and "RECURSO ESPECIAL & honorários" in result.data["text"]


async def test_get_publication_of_a_gone_item_is_not_found(djen: FakeDjen, mcp_client):
    publication_id = await _id_of(mcp_client, 0)
    djen.body = FakeDjen.fixture("empty.json")

    result = await mcp_client.call_tool(
        "get_publication", {"id": publication_id}, raise_on_error=False
    )

    assert result.is_error and json.loads(result.content[0].text)["code"] == "not_found"


async def test_get_publication_rejects_a_malformed_id(mcp_client):
    result = await mcp_client.call_tool("get_publication", {"id": "zzz"}, raise_on_error=False)

    assert result.is_error and json.loads(result.content[0].text)["code"] == "invalid_argument"
