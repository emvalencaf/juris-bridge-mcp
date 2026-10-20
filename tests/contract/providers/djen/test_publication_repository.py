import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from juris_bridge_mcp.adapters.djen.publication_repository import (
    RETRIED_STATUSES,
    DjenPublicationRepository,
)
from juris_bridge_mcp.adapters.http_client import UpstreamClient, build_http_client
from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure

FIXTURES = Path(__file__).parent / "fixtures"
DAY = date(2026, 10, 15)


class _OpenLimiter:
    async def acquire(self) -> None:
        return None


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def _repository(handler) -> DjenPublicationRepository:
    client = build_http_client(timeout_seconds=5, transport=httpx.MockTransport(handler))
    upstream = UpstreamClient(
        client,
        source="djen",
        limiter=_OpenLimiter(),
        max_retries=0,
        max_wait_seconds=1,
        retried_statuses=RETRIED_STATUSES,
    )
    return DjenPublicationRepository(upstream, base_url="https://djen.test")


def _respond(status: int, body=None, **kwargs):
    return lambda request: httpx.Response(status, json=body, **kwargs)


async def _search(handler, limit: int = 10):
    return await _repository(handler).search("tjsp", "recurso", DAY, DAY, limit=limit)


async def test_maps_the_recorded_publications():
    page = await _search(_respond(200, _fixture("tjsp_decisions.json")))

    first, second = page.publications
    assert (first.court, first.day, first.document_type) == ("tjsp", DAY, "DESPACHO/DECISÃO")
    assert first.number.digits == "12345677620258260100"
    assert first.number.formatted == "1234567-76.2025.8.26.0100"
    assert first.excerpt.startswith("DECISÃO Vistos. Trata-se de recurso especial")
    assert first.text_length == len(first.excerpt)
    assert first.url == "https://dje.example.test/publicacao/900000001"
    assert second.excerpt == (
        "Relator Fulano de Tal EMENTA: RECURSO ESPECIAL & honorários. "
        "Provimento negado. Acórdão unânime."
    )
    assert second.url is None
    assert first.id != second.id
    assert page.total == 2 and page.more is False


async def test_the_excerpt_is_cut_but_text_length_counts_the_whole_text():
    body = _fixture("tjsp_decisions.json")
    body["items"][0]["texto"] = "palavra " * 500

    first = (await _search(_respond(200, body))).publications[0]

    assert first.text_length == len("palavra " * 500) - 1
    assert len(first.excerpt) <= 501 and first.excerpt.endswith("…")


async def test_sends_the_query_as_is_with_the_court_and_window():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=_fixture("empty.json"))

    await _search(handler, limit=10)

    request = seen[0]
    assert request.url.path == "/api/v1/comunicacao"
    assert dict(request.url.params) == {
        "siglaTribunal": "TJSP",
        "texto": "recurso",
        "dataDisponibilizacaoInicio": "2026-10-15",
        "dataDisponibilizacaoFim": "2026-10-15",
        "itensPorPagina": "100",
        "pagina": "1",
    }


async def test_asks_for_5_items_when_the_limit_is_5_or_less():
    seen = []

    def handler(request):
        seen.append(request.url.params["itensPorPagina"])
        return httpx.Response(200, json=_fixture("empty.json"))

    await _search(handler, limit=3)

    assert seen == ["5"]


async def test_keeps_the_first_items_up_to_the_limit_and_says_more_follow():
    page = await _search(_respond(200, _fixture("tjsp_decisions.json")), limit=1)

    assert len(page.publications) == 1 and page.more is True


async def test_an_empty_answer_is_an_empty_page():
    page = await _search(_respond(200, _fixture("empty.json")))

    assert page.publications == () and page.total == 0 and page.more is False


async def _failure(handler) -> ToolFailure:
    with pytest.raises(ToolFailure) as caught:
        await _search(handler)
    return caught.value


async def test_429_is_rate_limited_with_a_wait_of_60_seconds():
    failure = await _failure(_respond(429))

    assert failure.code is ErrorCode.RATE_LIMITED and failure.retry_after_seconds == 60
    assert failure.source == "djen" and failure.retryable is True


async def test_403_is_a_blocked_source():
    failure = await _failure(_respond(403))

    assert failure.code is ErrorCode.SOURCE_BLOCKED and failure.retryable is False


@pytest.mark.parametrize("status", [500, 502, 503])
async def test_5xx_is_unavailable(status):
    failure = await _failure(_respond(status))

    assert failure.code is ErrorCode.SOURCE_UNAVAILABLE and failure.retryable is True


async def test_a_timeout_is_unavailable():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    assert (await _failure(handler)).code is ErrorCode.SOURCE_UNAVAILABLE


@pytest.mark.parametrize(
    "body",
    [
        {"status": "success"},
        {"items": "nope", "count": 1},
        {"items": [1], "count": 1},
        {"items": [{"texto": "x"}], "count": 1},
        {"items": [], "count": "many"},
    ],
)
async def test_an_unexpected_shape_is_source_changed(body):
    assert (await _failure(_respond(200, body))).code is ErrorCode.SOURCE_CHANGED


async def test_a_body_that_is_not_json_is_source_changed():
    failure = await _failure(_respond(200, content=b"<html>maintenance</html>"))

    assert failure.code is ErrorCode.SOURCE_CHANGED


async def test_an_unexpected_status_is_source_changed():
    assert (await _failure(_respond(418))).code is ErrorCode.SOURCE_CHANGED
