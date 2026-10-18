import json


async def _call(client, **arguments):
    result = await client.call_tool("search_legislation", arguments, raise_on_error=False)
    if result.is_error:
        return json.loads(result.content[0].text)
    return result.data


async def test_locates_a_norm_by_its_reference(mcp_client, senado):
    found = await _call(mcp_client, type="lei", number=14133, year=2021)

    assert found["source"] == "senado" and found["content_kind"] == "metadata"
    assert found["retrieved_at"].endswith("Z")
    assert found["total"] == 1 and found["next_cursor"] is None
    item = found["items"][0]
    assert item["urn"] == "urn:lex:br:federal:lei:2021-04-01;14133"
    assert item["citation"] == {
        "text": "Senado · Lei nº 14.133 de 01/04/2021",
        "url": "https://normas.leg.br/?urn=urn:lex:br:federal:lei:2021-04-01;14133",
    }
    assert item["type"] == "lei" and item["number"] == 14133 and item["year"] == 2021
    assert item["signed_on"] == "2021-04-01"
    assert item["summary"] == "Lei de Licitações e Contratos Administrativos."
    assert senado.requests[0].url.params["tipo"] == "LEI"


async def test_an_empty_search_returns_no_items(mcp_client, senado):
    senado.body = senado.fixture("empty.json")

    found = await _call(mcp_client, type="lei", number=1, year=1900)

    assert found["items"] == [] and found["total"] == 0 and found["next_cursor"] is None


async def test_pages_with_a_cursor(mcp_client, senado):
    senado.body = senado.fixture("lei_2021_five.json")
    numbers, cursor = [], None
    while True:
        page = await _call(mcp_client, type="lei", year=2021, limit=2, cursor=cursor)
        numbers += [item["number"] for item in page["items"]]
        cursor = page["next_cursor"]
        if cursor is None:
            break

    assert len(numbers) == 5 and len(set(numbers)) == 5


async def test_an_unknown_type_is_invalid_argument(mcp_client):
    error = await _call(mcp_client, type="portaria", number=1)

    assert error["code"] == "invalid_argument" and "lei-complementar" in error["hint"]


async def test_an_unavailable_source_is_reported(mcp_client, senado):
    senado.status = 503

    error = await _call(mcp_client, type="lei", number=14133, year=2021)

    assert error["code"] == "source_unavailable" and error["source"] == "senado"
    assert error["retryable"] is True


async def test_a_changed_source_is_reported(mcp_client, senado):
    senado.body = {"unexpected": True}

    error = await _call(mcp_client, type="lei", number=14133, year=2021)

    assert error["code"] == "source_changed" and error["source"] == "senado"


async def test_the_tool_is_listed_read_only(mcp_client):
    tools = {t.name: t for t in await mcp_client.list_tools()}

    assert tools["search_legislation"].annotations.read_only_hint is True
