import json
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from juris_bridge_mcp.adapters.datajud.case_repository import DatajudCaseRepository
from juris_bridge_mcp.adapters.http_client import UpstreamClient, build_http_client
from juris_bridge_mcp.domain.cnj_number import CnjNumber
from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure

FIXTURES = Path(__file__).parent / "fixtures"
NUMBER = CnjNumber.parse("00008323520184013202")


class _OpenLimiter:
    async def acquire(self) -> None:
        return None


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def _repository(handler) -> DatajudCaseRepository:
    client = build_http_client(timeout_seconds=5, transport=httpx.MockTransport(handler))
    upstream = UpstreamClient(
        client, source="datajud", limiter=_OpenLimiter(), max_retries=0, max_wait_seconds=1
    )
    return DatajudCaseRepository(
        upstream, base_url="https://datajud.test", api_key="the-public-key"
    )


def _respond(status: int, body) -> httpx.MockTransport:
    return lambda request: httpx.Response(status, json=body)


async def test_maps_the_recorded_case():
    record = await _repository(_respond(200, _fixture("trf1_hit.json"))).find(NUMBER, "trf1")

    case = record.case
    assert case.number == NUMBER
    assert case.court == "trf1"
    assert case.instance == "JE"
    assert case.filed_on == date(2018, 10, 29)
    assert (case.case_class.code, case.case_class.name) == (
        436,
        "Procedimento do Juizado Especial Cível",
    )
    assert [(s.code, s.name) for s in case.subjects] == [(6177, "Concessão")]
    assert (case.judging_body.code, case.judging_body.name) == (16403, "Tefé")
    assert case.secrecy_level == 0
    assert (case.source_system.code, case.source_system.name) == (1, "PJe")
    assert case.last_updated_at == datetime(2026, 6, 8, 14, 55, 23, 378000, tzinfo=UTC)
    assert len(case.events) == 43
    first = case.events[0]
    assert (first.term.code, first.term.name) == (26, "Distribuição")
    assert first.occurred_at == datetime(2018, 10, 30, 14, 6, 24, tzinfo=UTC)
    assert first.judging_body.code == 16403
    assert (first.complements[0].term.code, first.complements[0].term.name) == (
        2,
        "competência exclusiva",
    )
    assert first.complements[0].kind == "tipo_de_distribuicao_redistribuicao"
    assert record.raw["numeroProcesso"] == NUMBER.digits


async def test_queries_the_court_index_with_the_key():
    seen: list[httpx.Request] = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=_fixture("trf1_empty.json"))

    await _repository(handler).find(NUMBER, "tre-df")

    request = seen[0]
    assert str(request.url) == "https://datajud.test/api_publica_tre-df/_search"
    assert request.headers["Authorization"] == "APIKey the-public-key"
    assert json.loads(request.content)["query"] == {"match": {"numeroProcesso": NUMBER.digits}}


async def test_no_hit_is_none():
    assert (
        await _repository(_respond(200, _fixture("trf1_empty.json"))).find(NUMBER, "trf1") is None
    )


async def test_missing_optional_fields_become_none_and_empty():
    body = _fixture("trf1_hit.json")
    source = body["hits"]["hits"][0]["_source"]
    for key in ("assuntos", "movimentos", "classe", "sistema", "dataAjuizamento"):
        del source[key]

    case = (await _repository(_respond(200, body)).find(NUMBER, "trf1")).case

    assert case.subjects == () and case.events == ()
    assert case.case_class is None and case.source_system is None and case.filed_on is None


async def test_several_instances_pick_the_most_recently_updated():
    body = _fixture("trf1_hit.json")
    older = json.loads(json.dumps(body["hits"]["hits"][0]))
    older["_source"]["grau"] = "G1"
    older["_source"]["dataHoraUltimaAtualizacao"] = "2020-01-01T00:00:00.000Z"
    body["hits"]["hits"].append(older)

    record = await _repository(_respond(200, body)).find(NUMBER, "trf1")

    assert record.case.instance == "JE"
    assert record.matches == 2


@pytest.mark.parametrize(
    ("status", "code", "retryable"),
    [
        (401, ErrorCode.SOURCE_AUTH_FAILED, False),
        (500, ErrorCode.SOURCE_UNAVAILABLE, True),
        (503, ErrorCode.SOURCE_UNAVAILABLE, True),
        (400, ErrorCode.SOURCE_CHANGED, False),
        (404, ErrorCode.SOURCE_CHANGED, False),
    ],
)
async def test_http_failures_map_to_error_codes(status, code, retryable):
    with pytest.raises(ToolFailure) as caught:
        await _repository(_respond(status, {"error": "x"})).find(NUMBER, "trf1")

    assert caught.value.code is code
    assert caught.value.retryable is retryable
    assert caught.value.source == "datajud"


async def test_timeout_is_source_unavailable():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(ToolFailure) as caught:
        await _repository(handler).find(NUMBER, "trf1")

    assert caught.value.code is ErrorCode.SOURCE_UNAVAILABLE


async def test_elasticsearch_timed_out_is_source_unavailable():
    body = {**_fixture("trf1_empty.json"), "timed_out": True}

    with pytest.raises(ToolFailure) as caught:
        await _repository(_respond(200, body)).find(NUMBER, "trf1")

    assert caught.value.code is ErrorCode.SOURCE_UNAVAILABLE


def _drift(mutate):
    body = _fixture("trf1_hit.json")
    mutate(body["hits"]["hits"][0]["_source"], body)
    return body


@pytest.mark.parametrize(
    "mutate",
    [
        lambda s, b: b.update(hits="nope"),
        lambda s, b: s.update(dataAjuizamento="29/10/2018"),
        lambda s, b: s.update(movimentos="x"),
        lambda s, b: s.update(classe=7),
        lambda s, b: s.pop("numeroProcesso"),
        lambda s, b: s["movimentos"][0].update(dataHora="yesterday"),
        lambda s, b: s.update(nivelSigilo="high"),
        lambda s, b: s.update(dataHoraUltimaAtualizacao="2026-06-08T14:55:23"),
        lambda s, b: s["movimentos"][0].update(dataHora="2018-10-30T14:06:24"),
    ],
)
async def test_unexpected_shape_is_source_changed(mutate):
    with pytest.raises(ToolFailure) as caught:
        await _repository(_respond(200, _drift(mutate))).find(NUMBER, "trf1")

    assert caught.value.code is ErrorCode.SOURCE_CHANGED


async def test_non_json_body_is_source_changed():
    with pytest.raises(ToolFailure) as caught:
        await _repository(lambda r: httpx.Response(200, text="<html>")).find(NUMBER, "trf1")

    assert caught.value.code is ErrorCode.SOURCE_CHANGED


async def test_the_newest_record_is_chosen_by_instant_not_by_text():
    body = _fixture("trf1_hit.json")
    other = json.loads(json.dumps(body["hits"]["hits"][0]))
    other["_source"]["grau"] = "G2"
    # Later instant, but earlier as text because of the UTC offset.
    other["_source"]["dataHoraUltimaAtualizacao"] = "2026-06-08T12:00:00-03:00"
    body["hits"]["hits"].append(other)

    record = await _repository(_respond(200, body)).find(NUMBER, "trf1")

    assert record.case.instance == "G2"
