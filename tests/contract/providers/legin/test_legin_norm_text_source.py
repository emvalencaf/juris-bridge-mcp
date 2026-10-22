from pathlib import Path

import httpx
import pytest

from juris_bridge_mcp.adapters.http_client import UpstreamClient, build_http_client
from juris_bridge_mcp.adapters.legin.norm_text_source import LeginNormTextSource
from juris_bridge_mcp.adapters.legislation.norm_text_parser import parse_norm_text
from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure
from juris_bridge_mcp.domain.legislation import Urn

FIXTURES = Path(__file__).parent / "fixtures"
LEXML = "https://lexml.test"
SHEET_13105 = "/legin/fed/lei/2015/lei-13105-16-marco-2015-780273-norma-pl.html"
TEXT_13105 = "/legin/fed/lei/2015/lei-13105-16-marco-2015-780273-normaatualizada-pl.html"
CPC = Urn.parse("urn:lex:br:federal:lei:2015-03-16;13105")
UNKNOWN = Urn.parse("urn:lex:br:federal:lei:2019-09-24;13869")


class _OpenLimiter:
    async def acquire(self) -> None:
        return None


def _fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _source(handler) -> LeginNormTextSource:
    client = build_http_client(timeout_seconds=5, transport=httpx.MockTransport(handler))
    upstream = UpstreamClient(
        client, source="camara_legin", limiter=_OpenLimiter(), max_retries=0, max_wait_seconds=1
    )
    return LeginNormTextSource(upstream, lexml_base_url=LEXML)


class _Site:
    """The three hops, each scripted by path; every request is recorded in `paths`."""

    def __init__(self, **pages: bytes | int) -> None:
        self.pages: dict[str, bytes | int] = {
            f"/urn/{CPC.text}": _fixture("lexml_lei_13105_2015.htm"),
            f"/urn/{UNKNOWN.text}": _fixture("lexml_urn_not_found.htm"),
            SHEET_13105: _fixture("camara_sheet_lei_13105_2015.htm"),
            TEXT_13105: _fixture("camara_text_lei_13105_2015.htm"),
        }
        self.pages.update(pages)
        self.paths: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.paths.append(request.url.path)
        page = self.pages.get(request.url.path)
        if isinstance(page, int):
            return httpx.Response(page, content=b"refused")
        if page is None:
            return httpx.Response(404, content=b"not found")
        return httpx.Response(200, content=page, headers={"Content-Type": "text/html"})


async def test_resolves_the_text_through_the_urn_page_and_the_data_sheet():
    site = _Site()

    text = await _source(site).fetch(CPC)

    assert site.paths == [f"/urn/{CPC.text}", SHEET_13105, TEXT_13105]
    assert text is not None and text.source == "camara_legin"
    assert text.url == "https://www2.camara.leg.br" + TEXT_13105
    assert [a.key for a in text.articles] == [str(n) for n in range(1, 11)]
    assert text.articles[0].text.startswith("Art. 1º O processo civil será ordenado")


async def test_a_fallback_text_says_where_it_came_from_and_what_hints_at_amendments():
    text = await _source(_Site()).fetch(CPC)

    assert text is not None
    assert text.warnings[0].startswith("The text comes from the Câmara Legin, not the Planalto")
    hint = next(w for w in text.warnings if w.startswith("Amendment hints"))
    assert "data sheet, not from the text" in hint and "(Alteração)" in hint


async def test_the_sheet_remark_and_the_newest_amendments_are_passed_on():
    sheet = _fixture("camara_sheet_lei_14133_2021.htm")
    site = _Site(**{SHEET_13105: sheet})
    # The sheet of Lei 14.133 links its own text page, relative to where the sheet was served.
    site.pages["/legin/fed/lei/2015/lei-14133-1-abril-2021-791222-normaatualizada-pl.html"] = (
        site.pages[TEXT_13105]
    )

    text = await _source(site).fetch(CPC)

    assert text is not None
    remark = next(w for w in text.warnings if w.startswith("The Câmara data sheet remarks"))
    assert "Supremo Tribunal Federal" in remark
    hint = next(w for w in text.warnings if w.startswith("Amendment hints"))
    assert "Lei Ordinária nº 15471 de 20 de Julho de 2026" in hint
    assert "Decreto nº 13106" not in hint, "a regulation is not an amendment"
    assert hint.index("15471") < hint.index("15266")
    assert hint.count(" - (") == 5


async def test_without_an_updated_text_the_original_publication_is_used_and_flagged():
    sheet = _fixture("camara_sheet_lei_13105_2015.htm").replace(
        b"Texto Atualizado (HTML)", b"Outro formato"
    )
    original = (
        "/legin/fed/lei/2015/lei-13105-16-marco-2015-780273-publicacaooriginal-146341-pl.html"
    )
    site = _Site(**{SHEET_13105: sheet, original: _fixture("camara_text_lei_13105_2015.htm")})

    text = await _source(site).fetch(CPC)

    assert text is not None and text.url.endswith("publicacaooriginal-146341-pl.html")
    assert any("as originally published" in w for w in text.warnings)


async def test_a_urn_the_portal_does_not_know_has_no_text_and_no_further_request():
    site = _Site()

    assert await _source(site).fetch(UNKNOWN) is None
    assert site.paths == [f"/urn/{UNKNOWN.text}"]


async def test_a_norm_whose_sheet_is_missing_has_no_text():
    site = _Site()
    del site.pages[SHEET_13105]

    assert await _source(site).fetch(CPC) is None


async def test_a_sheet_that_links_no_text_gives_none():
    sheet = b"<html><body><div class='dadosNorma'><h1>LEI 1</h1></div></body></html>"

    assert await _source(_Site(**{SHEET_13105: sheet})).fetch(CPC) is None


async def test_the_portal_challenge_is_reported_as_blocked_and_never_solved():
    challenge = (
        b"<html><head><title>Verifica\xc3\xa7\xc3\xa3o de seguran\xc3\xa7a - Senado Federal"
        b"</title></head><body>JavaScript is required <script>fetch('/_challenge')</script>"
        b"</body></html>"
    )
    site = _Site(**{f"/urn/{CPC.text}": challenge})

    with pytest.raises(ToolFailure) as caught:
        await _source(site).fetch(CPC)

    assert caught.value.code is ErrorCode.SOURCE_BLOCKED and not caught.value.retryable
    assert caught.value.source == "camara_legin"
    assert site.paths == [f"/urn/{CPC.text}"]


async def test_a_page_the_portal_no_longer_serves_as_a_norm_page_is_source_changed():
    site = _Site(**{f"/urn/{CPC.text}": b"<html><body><h1>Novo portal</h1></body></html>"})

    with pytest.raises(ToolFailure) as caught:
        await _source(site).fetch(CPC)

    assert caught.value.code is ErrorCode.SOURCE_CHANGED


async def test_a_sheet_link_that_leaves_the_camara_site_is_refused():
    sheet = _fixture("camara_sheet_lei_13105_2015.htm").replace(
        b'href="lei-13105-16-marco-2015-780273-normaatualizada-pl.html"',
        b'href="https://evil.example/normaatualizada.html"',
    )

    with pytest.raises(ToolFailure) as caught:
        await _source(_Site(**{SHEET_13105: sheet})).fetch(CPC)

    assert caught.value.code is ErrorCode.SOURCE_CHANGED


async def test_a_gateway_error_served_with_status_200_is_unavailable_not_a_page():
    gateway = b"<html>\n<head><title>504 Gateway Time-out</title></head>\n<body></body></html>"

    with pytest.raises(ToolFailure) as caught:
        await _source(_Site(**{TEXT_13105: gateway})).fetch(CPC)

    assert caught.value.code is ErrorCode.SOURCE_UNAVAILABLE and caught.value.retryable


@pytest.mark.parametrize(
    ("status", "code"),
    [(403, ErrorCode.SOURCE_BLOCKED), (503, ErrorCode.SOURCE_UNAVAILABLE)],
)
async def test_a_refusal_or_an_outage_is_reported_with_its_code(status, code):
    with pytest.raises(ToolFailure) as caught:
        await _source(_Site(**{SHEET_13105: status})).fetch(CPC)

    assert caught.value.code is code and caught.value.source == "camara_legin"


async def test_a_jump_in_the_article_numbers_is_warned():
    page = _fixture("camara_text_lei_13105_2015.htm").decode()
    page = page.replace("Art. 4º ", "Art. 40 ").replace("Art. 5º ", "Art. 50 ")

    text = await _source(_Site(**{TEXT_13105: page.encode()})).fetch(CPC)

    assert text is not None
    jump = next(w for w in text.warnings if "jumps over article numbers" in w)
    assert "4-5" in jump and "11-39" in jump


def test_a_range_stub_stands_for_every_article_it_covers():
    html = (FIXTURES / "camara_text_codigo_civil_arts_754_805.htm").read_text(encoding="utf-8")

    text = parse_norm_text(html, url="u")

    revoked = {a.key for a in text.articles if a.flags == ("revoked",)}
    assert {str(n) for n in range(757, 778)} <= revoked
    assert "Arts. 757 a 777" in text.find_article("770")[0].text
    assert "Arts. 757" not in text.find_article("756")[0].text
    assert text.find_article("756")[0].flags == ()
    assert text.find_article("778")[0].text.startswith("Arts. 778 a 788.")
    assert text.find_article("803")[0].flags == ()


async def test_the_range_stubs_of_a_consolidated_text_leave_no_gap_to_warn_about():
    site = _Site(**{TEXT_13105: _fixture("camara_text_codigo_civil_arts_754_805.htm")})

    text = await _source(site).fetch(CPC)

    assert text is not None and not any("jumps" in w for w in text.warnings)
