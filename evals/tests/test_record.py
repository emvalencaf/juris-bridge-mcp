"""Record mode: only against a scripted upstream, never live."""

import json
import socket
from datetime import date
from pathlib import Path

import httpx
import pytest

from evals.cassette import Cassette, cassette_path, replay_session
from evals.record import (
    RECORD_ENV,
    RecordingDisabledError,
    RecordingTransport,
    RecordOptions,
    record_case,
    recording_session,
)

DJEN_FIXTURE = (
    Path(__file__).parents[2] / "tests/contract/providers/djen/fixtures/tjsp_decisions.json"
)
TODAY = date(2026, 10, 22)
CPF = "123.456.789-09"
CNPJ = "12.345.678/0001-95"
ENABLED = {RECORD_ENV: "1"}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(self, *args, **kwargs):
        raise AssertionError("record mode opened a network connection")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)


def upstream(body: bytes | None = None) -> httpx.MockTransport:
    payload = body if body is not None else DJEN_FIXTURE.read_bytes()
    return httpx.MockTransport(
        lambda request: httpx.Response(
            200, headers={"content-type": "application/json", "set-cookie": "s=1"}, content=payload
        )
    )


async def search(client):
    return await client.call_tool(
        "search_publications",
        {
            "court": "tjsp",
            "date_from": "2026-10-15",
            "date_to": "2026-10-15",
            "query": "recurso especial",
        },
        raise_on_error=False,
    )


async def test_without_the_variable_a_session_is_refused_and_nothing_is_sent():
    sent = []
    inner = httpx.MockTransport(lambda r: sent.append(r) or httpx.Response(200))

    with pytest.raises(RecordingDisabledError):
        async with recording_session("c1", RecordOptions(environ={}, inner=inner)):
            pass

    assert sent == []


async def test_a_value_other_than_one_is_refused_too():
    with pytest.raises(RecordingDisabledError):
        async with recording_session(
            "c1", RecordOptions(environ={RECORD_ENV: "true"}, inner=upstream())
        ):
            pass


async def test_record_case_saves_a_dated_cassette_named_after_the_case(tmp_path):
    path = await record_case(
        "case-001",
        search,
        root=tmp_path,
        options=RecordOptions(environ=ENABLED, inner=upstream(), today=TODAY),
    )

    assert path == cassette_path("case-001", root=tmp_path)
    saved = Cassette.load(path)
    assert saved.recorded_on == TODAY
    assert len(saved.entries) == 1


async def test_the_saved_cassette_holds_no_cpf_cnpj_or_name(tmp_path):
    body = json.dumps(
        {
            "items": [
                {
                    "texto": f"Autor: Maria Aparecida Souza, CPF {CPF}, CNPJ {CNPJ}",
                    "numero_processo": "0001234-56.2024.8.26.0100",
                }
            ],
            "count": 1,
        }
    ).encode()

    path = await record_case(
        "case-002",
        search,
        root=tmp_path,
        options=RecordOptions(environ=ENABLED, inner=upstream(body), today=TODAY),
    )

    text = path.read_text(encoding="utf-8")
    assert CPF not in text and CNPJ not in text and "Maria Aparecida" not in text
    assert "[CPF]" in text and "[PESSOA 1]" in text
    assert "0001234-56.2024.8.26.0100" in text
    entry = next(iter(Cassette.load(path).entries.values()))
    assert set(json.loads(entry.body)) == {"items", "count"}  # still JSON, keys kept
    assert "set-cookie" not in entry.headers


async def test_a_recorded_cassette_replays_through_the_replay_transport(tmp_path):
    path = await record_case(
        "case-003",
        search,
        root=tmp_path,
        options=RecordOptions(environ=ENABLED, inner=upstream(), today=TODAY),
    )

    async with replay_session(Cassette.load(path)) as session:
        result = await search(session.client)

    assert session.misses == 0
    assert not result.is_error


async def test_requests_are_paced_with_the_injected_clock():
    now = [100.0]
    waits: list[float] = []

    async def sleep(seconds: float) -> None:
        waits.append(seconds)
        now[0] += seconds

    transport = RecordingTransport(
        upstream(b"{}"),
        Cassette(recorded_on=TODAY),
        min_interval=2.0,
        clock=lambda: now[0],
        sleep=sleep,
    )
    async with httpx.AsyncClient(transport=transport) as client:
        await client.get("https://x.test/a")
        now[0] += 0.5
        await client.get("https://x.test/b")
        now[0] += 5.0
        await client.get("https://x.test/c")

    assert waits == [pytest.approx(1.5)]


async def test_a_failed_run_saves_nothing(tmp_path):
    async def run(client):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await record_case(
            "case-004",
            run,
            root=tmp_path,
            options=RecordOptions(environ=ENABLED, inner=upstream(), today=TODAY),
        )

    assert not cassette_path("case-004", root=tmp_path).exists()
