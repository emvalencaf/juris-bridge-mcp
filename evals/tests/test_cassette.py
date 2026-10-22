"""Cassette replay: a recorded request is answered, an unrecorded one is a counted miss."""

import json
import socket
from datetime import date
from pathlib import Path

import httpx
import pytest

from evals.cassette import (
    Cassette,
    CassetteEntry,
    ReplayTransport,
    cassette_path,
    replay_session,
    request_key,
)

DJEN_FIXTURE = (
    Path(__file__).parents[2] / "tests/contract/providers/djen/fixtures/tjsp_decisions.json"
)
SEARCH_URL = "https://comunicaapi.pje.jus.br/api/v1/comunicacao"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Fail the test if anything tries to open a real connection."""

    def refuse(self, *args, **kwargs):
        raise AssertionError("replay opened a network connection")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)


def djen_body() -> bytes:
    return DJEN_FIXTURE.read_bytes()


async def _search(client, **arguments):
    arguments = {
        "court": "tjsp",
        "date_from": "2026-10-15",
        "date_to": "2026-10-15",
        "query": "recurso especial",
        **arguments,
    }
    return await client.call_tool("search_publications", arguments, raise_on_error=False)


async def _miss_key() -> str:
    """The key of the request the server sends, learnt from an empty Cassette's miss."""
    async with replay_session(Cassette(recorded_on=date(2026, 10, 22))) as session:
        await _search(session.client)
        return session.transport.missed[0]


def test_the_key_ignores_query_order_and_headers_but_not_the_body():
    a = httpx.Request("GET", SEARCH_URL + "?b=2&a=1", headers={"Authorization": "x"})
    b = httpx.Request("GET", SEARCH_URL + "?a=1&b=2")
    c = httpx.Request("POST", SEARCH_URL, json={"q": 1})
    d = httpx.Request("POST", SEARCH_URL, json={"q": 2})

    assert request_key(a) == request_key(b)
    assert request_key(c) != request_key(d)
    assert request_key(a) != request_key(c)


def test_a_cassette_round_trips_through_json_named_after_the_case(tmp_path):
    entry = CassetteEntry.from_response("GET /x", 200, {"content-type": "text/html"}, b"\xff\xfe")
    cassette = Cassette(recorded_on=date(2026, 10, 22), entries={"GET /x": entry})
    path = cassette_path("lookup-1", root=tmp_path)

    cassette.save(path)

    assert path.name == "lookup-1.json"
    assert json.loads(path.read_text())["recorded_on"] == "2026-10-22"
    loaded = Cassette.load(path)
    assert loaded.recorded_on == date(2026, 10, 22)
    assert loaded.entries["GET /x"].body == b"\xff\xfe"


async def test_a_recorded_request_is_served_through_the_real_server():
    key = await _miss_key()
    entry = CassetteEntry.from_response(key, 200, {}, djen_body())
    cassette = Cassette(recorded_on=date(2026, 10, 1), entries={key: entry})

    async with replay_session(cassette) as session:
        result = await _search(session.client)

        assert not result.is_error
        assert result.data["items"][0]["cnj_number"] == "1234567-76.2025.8.26.0100"
        assert session.misses == 0


async def test_an_unrecorded_request_is_source_unavailable_and_counted():
    async with replay_session(Cassette(recorded_on=date(2026, 10, 1))) as session:
        result = await _search(session.client)

        assert result.is_error
        assert json.loads(result.content[0].text)["code"] == "source_unavailable"
        assert session.misses == 1


async def test_every_unrecorded_request_adds_to_the_miss_count():
    async with replay_session(Cassette(recorded_on=date(2026, 10, 1))) as session:
        await _search(session.client)
        await _search(session.client, query="agravo")

        assert session.misses == 2
        assert len(set(session.transport.missed)) == 2


async def test_the_cassette_carries_its_recording_date():
    async with replay_session(Cassette(recorded_on=date(2026, 9, 30))) as session:
        assert session.cassette.recorded_on == date(2026, 9, 30)


async def test_replay_never_reaches_the_network():
    transport = ReplayTransport(Cassette(recorded_on=date(2026, 10, 1)))
    async with httpx.AsyncClient(transport=transport) as client:
        response = await client.get("https://example.invalid/anything")

    assert response.status_code == 503 and transport.misses == 1
