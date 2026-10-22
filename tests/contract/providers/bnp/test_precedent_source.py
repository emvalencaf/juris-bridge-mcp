import json
import os
from datetime import UTC, date, datetime
from pathlib import Path

import httpx
import pytest

from juris_bridge_mcp.adapters.bnp.precedent_source import BnpPrecedentSource
from juris_bridge_mcp.adapters.http_client import UpstreamClient, build_http_client
from juris_bridge_mcp.config.bnp import BnpSettings
from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure
from juris_bridge_mcp.domain.precedent import PrecedentFilters

FIXTURES = Path(__file__).parent / "fixtures"


class _OpenLimiter:
    async def acquire(self) -> None:
        return None


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def _source(handler=None, *, transport=None) -> BnpPrecedentSource:
    client = build_http_client(
        timeout_seconds=30, transport=transport or httpx.MockTransport(handler)
    )
    upstream = UpstreamClient(
        client, source="bnp", limiter=_OpenLimiter(), max_retries=0, max_wait_seconds=1
    )
    return BnpPrecedentSource(upstream, base_url=BnpSettings().base_url)


def _answering(body: dict):
    return lambda request: httpx.Response(200, json=body)


async def test_maps_a_repercussao_geral_theme():
    page = await _source(_answering(_fixture("stf_rg_1002.json"))).search(
        PrecedentFilters(), page=1, limit=10
    )

    precedent = page.precedents[0]
    assert (precedent.id, precedent.body, precedent.court, precedent.kind) == (
        "stf-rg-1002",
        "STF",
        "stf",
        "RG",
    )
    assert precedent.number == "1002" and precedent.updated_on == date(2026, 10, 15)
    assert precedent.status_history[0].recorded_at == datetime(2026, 10, 13, 3, tzinfo=UTC)
    assert precedent.leading_cases[0].cnj_number is None
    assert page.total == 1 and page.total_is_capped is False


async def test_maps_a_string_number_and_the_dates_of_a_status_step():
    page = await _source(_answering(_fixture("trt04_oj_11.json"))).search(
        PrecedentFilters(), page=1, limit=10
    )

    precedent = page.precedents[0]
    assert precedent.id == "trt04-oj-11" and precedent.court == "trt4"
    step = precedent.status_history[0]
    assert (step.status, step.admitted_on, step.judged_on, step.published_on) == (
        "Admitido",
        date(2025, 11, 24),
        date(2026, 4, 29),
        date(2026, 4, 30),
    )
    assert precedent.question is None


async def test_a_drifted_search_is_source_changed():
    for body in ({"total": "many", "resultados": []}, {"total": 1}, {"resultados": []}):
        with pytest.raises(ToolFailure) as caught:
            await _source(_answering(body)).search(PrecedentFilters(), page=1, limit=10)
        assert caught.value.code is ErrorCode.SOURCE_CHANGED


async def test_a_result_without_an_identity_is_source_changed():
    body = {"total": 1, "resultados": [{"questao": "orphan"}]}

    with pytest.raises(ToolFailure) as caught:
        await _source(_answering(body)).search(PrecedentFilters(), page=1, limit=10)

    assert caught.value.code is ErrorCode.SOURCE_CHANGED


# Opt-in drift check: asks the live BNP for a record the cassettes hold. Run it with
# `JURIS_BRIDGE_LIVE_BNP=1 uv run pytest tests/contract/providers/bnp -k live`.
live = pytest.mark.skipif(
    os.environ.get("JURIS_BRIDGE_LIVE_BNP") != "1", reason="set JURIS_BRIDGE_LIVE_BNP=1 to run"
)


@live
async def test_live_bnp_still_answers_in_the_recorded_shape():
    source = _source(transport=httpx.AsyncHTTPTransport())

    record = await source.find("stf-rg-1002")
    decisions = await source.decisions("stf-rg-1002")
    page = await source.search(PrecedentFilters(court="stj", kind="RR"), page=1, limit=2)

    assert record is not None and record.precedent.thesis
    assert decisions.reporter is not None
    assert page.total > 0 and page.precedents[0].kind == "RR"
