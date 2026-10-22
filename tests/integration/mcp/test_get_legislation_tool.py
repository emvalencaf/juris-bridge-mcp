import json

import pytest

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


PAGE = "_ato2019-2022/2021/lei/l14133.htm"


@pytest.fixture
def lei_14133(senado, planalto):
    senado.body = senado.fixture("lei_14133_2021_detail.json")
    planalto.pages[PAGE] = planalto.fixture("lei_14133_2021.htm")


async def test_include_text_returns_the_plain_text_as_full_text(mcp_client, lei_14133, planalto):
    norm = await _call(mcp_client, urn=URN, include_text=True, max_chars=500)

    assert norm["content_kind"] == "full_text" and norm["source"] == "senado"
    assert len(norm["text"]) == 500 and norm["truncated"] is True
    assert norm["next_text_cursor"] and norm["text_source"] == "planalto"
    assert norm["text_url"].endswith(PAGE) and "article" not in norm
    assert norm["name"] == "Lei nº 14.133 de 01/04/2021"
    assert planalto.requests[-1].url.path == "/ccivil_03/" + PAGE


async def test_the_text_is_read_in_pieces_until_done(mcp_client, lei_14133):
    pieces, cursor = [], None
    while True:
        norm = await _call(
            mcp_client, urn=URN, include_text=True, max_chars=3000, text_cursor=cursor
        )
        pieces.append(norm["text"])
        cursor = norm["next_text_cursor"]
        if not norm["truncated"]:
            break

    whole = await _call(mcp_client, urn=URN, include_text=True, max_chars=100_000)
    assert len(pieces) > 1 and "".join(pieces) == whole["text"] and cursor is None


async def test_slices_and_articles_reuse_the_page_the_first_call_fetched(
    mcp_client, lei_14133, planalto
):
    first = await _call(mcp_client, urn=URN, include_text=True, max_chars=3000)
    fetched = len(planalto.requests)

    await _call(
        mcp_client,
        urn=URN,
        include_text=True,
        max_chars=3000,
        text_cursor=first["next_text_cursor"],
    )
    await _call(mcp_client, urn=URN, article="Art. 1º")

    assert fetched > 0 and len(planalto.requests) == fetched


async def test_the_default_slice_is_20000_characters(mcp_client, lei_14133):
    norm = await _call(mcp_client, urn=URN, include_text=True)

    assert len(norm["text"]) <= 20_000 and norm["content_kind"] == "full_text"


async def test_an_article_returns_that_article_only(mcp_client, lei_14133):
    norm = await _call(mcp_client, urn=URN, article="Art. 1º")

    assert norm["content_kind"] == "full_text" and norm["truncated"] is False
    assert norm["article"] == {"label": "Art. 1º", "flags": []}
    assert norm["text"].startswith("Art. 1º Esta Lei estabelece") and "Art. 2º" not in norm["text"]


async def test_a_struck_article_is_flagged_and_the_repeat_is_warned(mcp_client, lei_14133):
    norm = await _call(mcp_client, urn=URN, article="191")

    assert norm["article"]["label"] == "Art. 191" and norm["article"]["flags"] == []
    assert "3 times" in norm["warnings"][0]


async def test_an_article_the_parser_cannot_locate_is_not_found(mcp_client, lei_14133):
    error = await _call(mcp_client, urn=URN, article="Art. 99")

    assert error["code"] == "not_found" and error["source"] == "planalto"
    assert "Art. 99" in error["message"]


async def test_a_norm_without_a_planalto_page_returns_metadata_and_a_warning(mcp_client, senado):
    senado.body = senado.fixture("lei_14133_2021_detail.json")

    norm = await _call(mcp_client, urn=URN, include_text=True)

    assert norm["content_kind"] == "metadata" and "text" not in norm
    assert "Neither the Planalto nor the Câmara Legin" in norm["warnings"][0]
    assert "only metadata" in norm["warnings"][0]


async def test_a_planalto_refusal_is_source_blocked(mcp_client, lei_14133, planalto):
    planalto.status = 403

    error = await _call(mcp_client, urn=URN, include_text=True)

    assert error["code"] == "source_blocked" and error["source"] == "planalto"


async def test_a_page_the_parser_no_longer_reads_is_source_changed(mcp_client, lei_14133, planalto):
    planalto.pages[PAGE] = b"<html><body>" + b"<p>Portal novo.</p>" * 30 + b"</body></html>"

    error = await _call(mcp_client, urn=URN, include_text=True)

    assert error["code"] == "source_changed" and error["source"] == "planalto"


async def test_the_planalto_is_not_asked_for_metadata_only(mcp_client, lei_14133, planalto):
    await _call(mcp_client, urn=URN)

    assert planalto.requests == []


async def test_a_bad_article_or_slice_size_is_invalid_argument(mcp_client, lei_14133):
    for arguments in ({"article": "section"}, {"include_text": True, "max_chars": 0}):
        error = await _call(mcp_client, urn=URN, **arguments)

        assert error["code"] == "invalid_argument"


async def test_a_changed_source_is_reported(mcp_client, senado):
    senado.body = {"unexpected": True}

    error = await _call(mcp_client, urn=URN)

    assert error["code"] == "source_changed" and error["source"] == "senado"


async def test_the_tool_is_listed_read_only(mcp_client):
    tools = {t.name: t for t in await mcp_client.list_tools()}

    assert tools["get_legislation"].annotations.read_only_hint is True


async def test_annotations_can_be_left_out_of_the_text(mcp_client, lei_14133):
    with_notes = await _call(mcp_client, urn=URN, include_text=True, max_chars=100_000)
    without = await _call(
        mcp_client, urn=URN, include_text=True, max_chars=100_000, include_annotations=False
    )

    assert "(Vide Decreto" in with_notes["text"] and "(Vide Decreto" not in without["text"]
    assert "(Revogado" in with_notes["text"] and "(Revogado" in without["text"]
    assert len(without["text"]) < len(with_notes["text"])
    assert any("include_annotations" in w for w in without["warnings"])


async def test_the_tool_describes_include_annotations(mcp_client):
    tools = {t.name: t for t in await mcp_client.list_tools()}

    assert "include_annotations" in tools["get_legislation"].input_schema["properties"]
    assert "include_annotations=false" in tools["get_legislation"].description


CPC = "urn:lex:br:federal:lei:2015-03-16;13105"


@pytest.fixture
def cpc_on_legin(senado, legin):
    senado.body = senado.fixture("lei_14133_2021_detail.json")
    legin.serve_cpc()


async def test_when_the_planalto_has_no_page_the_camara_legin_supplies_the_text(
    mcp_client, cpc_on_legin, planalto
):
    norm = await _call(mcp_client, urn=CPC, include_text=True)

    assert norm["content_kind"] == "full_text" and norm["text_source"] == "camara_legin"
    assert norm["text_url"].startswith("https://www2.camara.leg.br/legin/")
    assert "Art. 1º O processo civil será ordenado" in norm["text"]
    assert norm["warnings"][0].startswith("The Planalto has no text page")
    assert any("Câmara Legin, not the Planalto" in w for w in norm["warnings"])
    assert any(w.startswith("Amendment hints") for w in norm["warnings"])
    assert planalto.requests, "the Planalto is asked first"


async def test_an_article_can_be_read_from_the_fallback_text(mcp_client, cpc_on_legin):
    norm = await _call(mcp_client, urn=CPC, article="Art. 3º")

    assert norm["text_source"] == "camara_legin" and norm["article"]["label"] == "Art. 3º"
    assert norm["text"].startswith("Art. 3º Não se excluirá")


async def test_a_missing_article_names_the_source_that_was_read(mcp_client, cpc_on_legin):
    error = await _call(mcp_client, urn=CPC, article="Art. 99")

    assert error["code"] == "not_found" and error["source"] == "camara_legin"


async def test_a_planalto_refusal_falls_back_to_the_camara_legin(
    mcp_client, cpc_on_legin, planalto
):
    planalto.status = 403

    norm = await _call(mcp_client, urn=CPC, include_text=True)

    assert norm["text_source"] == "camara_legin"
    assert "The Planalto failed (source_blocked)" in norm["warnings"][0]


async def test_the_camara_legin_is_not_asked_for_metadata_only(mcp_client, cpc_on_legin, legin):
    await _call(mcp_client, urn=CPC)

    assert legin.requests == []


async def test_the_fallback_text_is_cached_with_its_warnings(mcp_client, cpc_on_legin, legin):
    first = await _call(mcp_client, urn=CPC, include_text=True)
    fetched = len(legin.requests)
    second = await _call(mcp_client, urn=CPC, include_text=True, max_chars=50)

    assert len(legin.requests) == fetched
    assert second["warnings"] == first["warnings"]
