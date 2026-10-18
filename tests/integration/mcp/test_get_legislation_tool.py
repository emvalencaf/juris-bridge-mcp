import json

URN = "urn:lex:br:federal:lei:2021-04-01;14133"


async def _call(client, **arguments):
    result = await client.call_tool("get_legislation", arguments, raise_on_error=False)
    if result.is_error:
        return json.loads(result.content[0].text)
    return result.data


async def test_returns_metadata_publications_and_bounded_relations(mcp_client, senado):
    senado.body = senado.fixture("lei_14133_2021_detail.json")

    norm = await _call(mcp_client, urn=URN, relations_limit=3)

    assert norm["source"] == "senado" and norm["content_kind"] == "metadata"
    assert norm["retrieved_at"].endswith("Z")
    assert norm["urn"] == URN and norm["type"] == "lei" and norm["number"] == 14133
    assert norm["year"] == 2021 and norm["signed_on"] == "2021-04-01"
    assert norm["name"] == "Lei nº 14.133 de 01/04/2021"
    assert norm["nickname"] == "Lei de Licitações e Contratos (2021)"
    assert norm["summary"] == "Lei de Licitações e Contratos Administrativos."
    assert norm["citation"] == {
        "text": "Senado · Lei nº 14.133 de 01/04/2021",
        "url": "https://normas.leg.br/?urn=" + URN,
    }
    assert norm["publications"][0]["published_on"] == "2021-04-01"
    assert len(norm["relations"]) == 3 and norm["relations_total"] > 3
    assert norm["relations"][0]["signed_on"] >= norm["relations"][1]["signed_on"]
    assert "raw" not in norm
    assert senado.requests[0].url.params["urn"] == URN


async def test_relations_default_to_25(mcp_client, senado):
    senado.body = senado.fixture("lei_14133_2021_detail.json")

    norm = await _call(mcp_client, urn=URN)

    assert len(norm["relations"]) == 25


async def test_a_urn_the_source_does_not_know_is_not_found(mcp_client, senado):
    senado.body = {"DetalheDocumento": {"documentos": ""}}

    error = await _call(mcp_client, urn=URN)

    assert error["code"] == "not_found" and error["source"] == "senado"


async def test_include_raw_attaches_the_upstream_payload(mcp_client, senado):
    senado.body = senado.fixture("lei_14133_2021_detail.json")

    norm = await _call(mcp_client, urn=URN, include_raw=True)

    assert norm["raw"]["unstable"] is True and "DetalheDocumento" in norm["raw"]["payload"]


async def test_a_malformed_urn_is_invalid_argument(mcp_client, senado):
    error = await _call(mcp_client, urn="Lei 14.133/2021")

    assert error["code"] == "invalid_argument" and senado.requests == []


async def test_the_text_is_not_covered_yet(mcp_client):
    error = await _call(mcp_client, urn=URN, include_text=True)

    assert error["code"] == "not_covered"


async def test_a_changed_source_is_reported(mcp_client, senado):
    senado.body = {"unexpected": True}

    error = await _call(mcp_client, urn=URN)

    assert error["code"] == "source_changed" and error["source"] == "senado"


async def test_the_tool_is_listed_read_only(mcp_client):
    tools = {t.name: t for t in await mcp_client.list_tools()}

    assert tools["get_legislation"].annotations.read_only_hint is True
