from pathlib import Path

import httpx
import pytest

from juris_bridge_mcp.adapters.http_client import UpstreamClient, build_http_client
from juris_bridge_mcp.adapters.planalto.norm_text_parser import parse_norm_text
from juris_bridge_mcp.adapters.planalto.norm_text_source import (
    PlanaltoNormTextSource,
    candidate_paths,
)
from juris_bridge_mcp.adapters.schema_drift import SchemaDrift
from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure
from juris_bridge_mcp.domain.legislation import Urn

FIXTURES = Path(__file__).parent / "fixtures"
BASE = "https://planalto.test/ccivil_03"
LEI_14133 = Urn.parse("urn:lex:br:federal:lei:2021-04-01;14133")


class _OpenLimiter:
    async def acquire(self) -> None:
        return None


def _page(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _parse(name: str):
    return parse_norm_text((FIXTURES / name).read_bytes().decode("cp1252"), url="u")


def _source(handler) -> PlanaltoNormTextSource:
    client = build_http_client(timeout_seconds=5, transport=httpx.MockTransport(handler))
    upstream = UpstreamClient(
        client, source="planalto", limiter=_OpenLimiter(), max_retries=0, max_wait_seconds=1
    )
    return PlanaltoNormTextSource(upstream, base_url=BASE)


def _serve(status: int, body: bytes = b""):
    return lambda request: httpx.Response(status, content=body)


def test_locates_each_article_of_the_recorded_norm():
    text = _parse("lei_14133_2021.htm")

    keys = [a.key for a in text.articles]
    assert keys == ["1", "2", "189", "190", "191", "191", "191"]
    first = text.articles[0]
    assert first.label == "Art. 1º" and first.flags == ()
    assert first.text.startswith("Art. 1º Esta Lei estabelece normas gerais de licitação")
    assert "Administrações Públicas diretas" in first.text
    assert "I - os órgãos dos Poderes Legislativo" in first.text
    assert "§ 1º Não são abrangidas por esta Lei as empresas públicas" in first.text


def test_an_article_ends_at_the_next_article_and_never_swallows_the_closing():
    text = _parse("lei_14133_2021.htm")

    second = text.articles[1].text
    assert second.startswith("Art. 2º") and "Art. 3º" not in second
    assert "Brasília" not in text.articles[3].text
    assert "Brasília," in text.text


def test_a_struck_article_is_flagged_superseded():
    text = _parse("lei_14133_2021.htm")

    old_wording = text.articles[4]
    assert old_wording.key == "191" and old_wording.flags == ("superseded",)
    assert (
        "Parágrafo único" in old_wording.text
        and "(Revogado pela Medida Provisória" in old_wording.text
    )


def test_a_repeated_article_resolves_to_the_wording_that_is_not_struck():
    text = _parse("lei_14133_2021.htm")

    article, occurrences = text.find_article("191")

    assert occurrences == 3 and article is text.articles[6] and article.flags == ()


def test_an_article_repealed_by_note_is_flagged_revoked():
    text = _parse("codigo_penal_arts_184_189.htm")

    revoked = {a.key: a.flags for a in text.articles}
    assert revoked["185"] == ("revoked",) and revoked["187"] == ("revoked",)
    assert revoked["184"] == () and revoked["186"] == ()
    assert text.find_article("185")[0].text.startswith("Art. 185 -")


def test_the_text_is_plain_and_decoded():
    text = _parse("lei_14133_2021.htm").text

    assert "<" not in text and "&nbsp;" not in text and "\xa0" not in text
    assert "Administrações" in text and "licitação" in text
    assert "  " not in text and "{" not in text


def test_a_page_without_articles_is_schema_drift():
    page = (
        "<html><body>"
        + "<p>Verificação de segurança do Senado Federal.</p>" * 10
        + "</body></html>"
    )

    with pytest.raises(SchemaDrift):
        parse_norm_text(page, url="u")


def test_an_almost_empty_page_is_schema_drift():
    with pytest.raises(SchemaDrift):
        parse_norm_text("<html><body><p>Art. 1º x</p></body></html>", url="u")


async def test_fetches_and_parses_the_norm_page():
    seen = []

    def handler(request):
        seen.append(request.url.path)
        if request.url.path.endswith("/l14133.htm"):
            return httpx.Response(200, content=_page("lei_14133_2021.htm"))
        return httpx.Response(404)

    text = await _source(handler).fetch(LEI_14133)

    assert seen[0] == "/ccivil_03/_ato2019-2022/2021/lei/l14133compilado.htm"
    assert seen[-1] == "/ccivil_03/_ato2019-2022/2021/lei/l14133.htm"
    assert text.url == f"{BASE}/_ato2019-2022/2021/lei/l14133.htm"
    assert text.articles[0].key == "1"


async def test_the_consolidated_page_wins_over_the_text_as_first_published():
    seen = []

    def handler(request):
        seen.append(request.url.path)
        return httpx.Response(200, content=_page("lei_14133_2021.htm"))

    text = await _source(handler).fetch(LEI_14133)

    assert len(seen) == 1 and text.url.endswith("/l14133compilado.htm")


async def test_tries_the_next_candidate_after_a_404():
    paths = []

    def handler(request):
        paths.append(request.url.path)
        if "lcp" in request.url.path:
            return httpx.Response(200, content=_page("lei_14133_2021.htm"))
        return httpx.Response(404)

    urn = Urn.parse("urn:lex:br:federal:lei.complementar:2019-04-08;166")
    text = await _source(handler).fetch(urn)

    assert paths == ["/ccivil_03/leis/lcp/lcp166.htm"] and text is not None


async def test_a_norm_with_no_page_is_none():
    assert await _source(_serve(404)).fetch(LEI_14133) is None


async def test_a_norm_type_without_a_known_path_is_none_and_asks_nothing():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200)

    urn = Urn.parse("urn:lex:br:federal:mensagem:2021-04-01;100")

    assert await _source(handler).fetch(urn) is None and seen == []


@pytest.mark.parametrize("status", [401, 403, 406])
async def test_a_refusal_is_source_blocked(status):
    with pytest.raises(ToolFailure) as caught:
        await _source(_serve(status)).fetch(LEI_14133)

    assert caught.value.code is ErrorCode.SOURCE_BLOCKED and caught.value.source == "planalto"
    assert not caught.value.retryable


async def test_html_that_no_longer_matches_the_parser_is_source_changed():
    page = b"<html><body>" + b"<p>Nova versao do portal sem artigos.</p>" * 10 + b"</body></html>"

    with pytest.raises(ToolFailure) as caught:
        await _source(_serve(200, page)).fetch(LEI_14133)

    assert caught.value.code is ErrorCode.SOURCE_CHANGED and caught.value.source == "planalto"


async def test_a_server_error_is_unavailable_and_retryable():
    with pytest.raises(ToolFailure) as caught:
        await _source(_serve(500)).fetch(LEI_14133)

    assert caught.value.code is ErrorCode.SOURCE_UNAVAILABLE and caught.value.retryable


async def test_a_network_failure_is_unavailable():
    def handler(request):
        raise httpx.ConnectTimeout("slow", request=request)

    with pytest.raises(ToolFailure) as caught:
        await _source(handler).fetch(LEI_14133)

    assert caught.value.code is ErrorCode.SOURCE_UNAVAILABLE


async def test_an_unexpected_status_is_source_changed():
    with pytest.raises(ToolFailure) as caught:
        await _source(_serve(418)).fetch(LEI_14133)

    assert caught.value.code is ErrorCode.SOURCE_CHANGED


async def test_decodes_utf8_pages_too():
    body = ("<html><body>" + "<p>Art. 1º Código é lei.</p>" * 20 + "</body></html>").encode()

    text = await _source(_serve(200, body)).fetch(LEI_14133)

    assert "Código é lei" in text.articles[0].text


@pytest.mark.parametrize(
    ("urn", "first", "plain"),
    [
        ("urn:lex:br:federal:lei:2021-04-01;14133", "_ato2019-2022/2021/lei/l14133", True),
        ("urn:lex:br:federal:lei:2024-01-02;15000", "_ato2023-2026/2024/lei/l15000", True),
        ("urn:lex:br:federal:lei:2005-02-09;11101", "_ato2004-2006/2005/lei/l11101", True),
        ("urn:lex:br:federal:lei:2002-01-10;10406", "leis/2002/l10406", True),
        ("urn:lex:br:federal:decreto:2022-01-01;11129", "_ato2019-2022/2022/decreto/d11129", True),
        ("urn:lex:br:federal:decreto.lei:1940-12-07;2848", "decreto-lei/del2848", True),
    ],
)
def test_candidate_paths_prefer_the_consolidated_page(urn, first, plain):
    paths = candidate_paths(Urn.parse(urn))

    assert paths[:3] == [f"{first}{s}.htm" for s in ("compilado", "compilada", "cons")]
    assert paths[3] == f"{first}.htm" and plain


@pytest.mark.parametrize(
    ("urn", "first"),
    [
        (
            "urn:lex:br:federal:medida.provisoria:2019-01-01;870",
            "_ato2019-2022/2019/mpv/mpv870.htm",
        ),
        ("urn:lex:br:federal:lei.complementar:2019-04-08;166", "leis/lcp/lcp166.htm"),
        (
            "urn:lex:br:federal:emenda.constitucional:2022-01-01;132",
            "constituicao/emendas/emc/emc132.htm",
        ),
    ],
)
def test_candidate_paths_for_norms_without_a_consolidated_page(urn, first):
    assert candidate_paths(Urn.parse(urn))[0] == first
