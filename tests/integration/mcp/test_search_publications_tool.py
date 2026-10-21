import json

from tests.integration.mcp.conftest import FakeDjen


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


async def test_a_djen_failure_carries_its_error_code(djen: FakeDjen, mcp_client):
    djen.status = 429

    error = await _call(mcp_client)

    assert error["code"] == "rate_limited" and error["retry_after_seconds"] == 60
    assert len(djen.requests) == 1


async def test_the_kind_filter_keeps_only_that_kind(djen: FakeDjen, mcp_client):
    page = await _call(mcp_client, kind="acordao")

    assert [item["kind"] for item in page["items"]] == ["acordao"]


async def test_an_unknown_kind_never_calls_the_djen(djen: FakeDjen, mcp_client):
    error = await _call(mcp_client, kind="despacho")

    assert error["code"] == "invalid_argument" and djen.requests == []
