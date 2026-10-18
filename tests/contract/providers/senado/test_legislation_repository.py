import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from juris_bridge_mcp.adapters.http_client import UpstreamClient, build_http_client
from juris_bridge_mcp.adapters.senado.legislation_repository import SenadoLegislationRepository
from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure
from juris_bridge_mcp.domain.legislation import LegislationFilters

FIXTURES = Path(__file__).parent / "fixtures"
LEI_14133 = LegislationFilters(norm_type="lei", number=14133, year=2021)


class _OpenLimiter:
    async def acquire(self) -> None:
        return None


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def _repository(handler) -> SenadoLegislationRepository:
    client = build_http_client(timeout_seconds=5, transport=httpx.MockTransport(handler))
    upstream = UpstreamClient(
        client, source="senado", limiter=_OpenLimiter(), max_retries=0, max_wait_seconds=1
    )
    return SenadoLegislationRepository(upstream, base_url="https://senado.test/dadosabertos")


def _respond(status: int, body):
    return lambda request: httpx.Response(status, json=body)


async def test_maps_the_recorded_norm():
    page = await _repository(_respond(200, _fixture("lei_14133_2021.json"))).search(
        LEI_14133, limit=10, offset=0
    )

    assert page.total == 1 and page.next_offset is None
    norm = page.norms[0]
    assert norm.urn == "urn:lex:br:federal:lei:2021-04-01;14133"
    assert (norm.norm_type, norm.number, norm.year) == ("lei", 14133, 2021)
    assert norm.signed_on == date(2021, 4, 1)
    assert norm.name == "Lei nº 14.133 de 01/04/2021"
    assert norm.summary == "Lei de Licitações e Contratos Administrativos."
    assert norm.nickname == "Lei de Licitações e Contratos (2021)"
    assert norm.citation_url == "https://normas.leg.br/?urn=urn:lex:br:federal:lei:2021-04-01;14133"


async def test_asks_the_lista_service_by_type_number_and_year():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=_fixture("lei_14133_2021.json"))

    await _repository(handler).search(LEI_14133, limit=10, offset=0)

    request = seen[0]
    assert request.url.path == "/dadosabertos/legislacao/lista"
    assert dict(request.url.params) == {"tipo": "LEI", "numero": "14133", "ano": "2021", "v": "3"}
    assert request.headers["accept"] == "application/json"


async def test_an_empty_answer_is_an_empty_page():
    page = await _repository(_respond(200, _fixture("empty.json"))).search(
        LEI_14133, limit=10, offset=0
    )

    assert page.norms == () and page.total == 0 and page.next_offset is None


@pytest.mark.parametrize("documentos", [None, {}], ids=["null", "empty-object"])
async def test_other_spellings_of_nothing_found_are_an_empty_page(documentos):
    body = {"ListaDocumento": {"documentos": documentos}}

    page = await _repository(_respond(200, body)).search(LEI_14133, limit=10, offset=0)

    assert page.norms == () and page.total == 0


async def test_pages_over_the_whole_answer_by_offset():
    repository = _repository(_respond(200, _fixture("lei_2021_five.json")))
    year = LegislationFilters(norm_type="lei", year=2021)

    first = await repository.search(year, limit=2, offset=0)
    last = await repository.search(year, limit=2, offset=4)

    assert (first.total, len(first.norms), first.next_offset) == (5, 2, 2)
    assert (last.total, len(last.norms), last.next_offset) == (5, 1, None)
    assert first.norms[0].number == 14288


@pytest.mark.parametrize(
    ("status", "code"),
    [(500, ErrorCode.SOURCE_UNAVAILABLE), (503, ErrorCode.SOURCE_UNAVAILABLE)],
)
async def test_an_unavailable_source_is_retryable(status, code):
    with pytest.raises(ToolFailure) as caught:
        await _repository(_respond(status, {})).search(LEI_14133, limit=10, offset=0)

    assert caught.value.code is code
    assert caught.value.retryable is True and caught.value.source == "senado"


async def test_a_timeout_is_source_unavailable():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(ToolFailure) as caught:
        await _repository(handler).search(LEI_14133, limit=10, offset=0)

    assert caught.value.code is ErrorCode.SOURCE_UNAVAILABLE


@pytest.mark.parametrize(
    "body",
    [
        {"unexpected": True},
        {"ListaDocumento": {"documentos": {"documento": "nope"}}},
        {"ListaDocumento": {"documentos": {"documento": [{"numero": "1"}]}}},
        {
            "ListaDocumento": {
                "documentos": {
                    "documento": [
                        {
                            "tipo": "LEI-n",
                            "numero": "1",
                            "normaNome": "x",
                            "dataassinatura": "not-a-date",
                        }
                    ]
                }
            }
        },
    ],
)
async def test_an_unexpected_shape_is_source_changed(body):
    with pytest.raises(ToolFailure) as caught:
        await _repository(_respond(200, body)).search(LEI_14133, limit=10, offset=0)

    assert caught.value.code is ErrorCode.SOURCE_CHANGED and caught.value.retryable is False


async def test_a_body_that_is_not_json_is_source_changed():
    def handler(request):
        return httpx.Response(200, text="<html>challenge</html>")

    with pytest.raises(ToolFailure) as caught:
        await _repository(handler).search(LEI_14133, limit=10, offset=0)

    assert caught.value.code is ErrorCode.SOURCE_CHANGED


async def test_an_unexpected_status_is_source_changed():
    with pytest.raises(ToolFailure) as caught:
        await _repository(_respond(404, {})).search(LEI_14133, limit=10, offset=0)

    assert caught.value.code is ErrorCode.SOURCE_CHANGED
