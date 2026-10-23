"""The drafted Precedent, negative and Coverage Eval cases load and replay offline."""

import json
import socket

import pytest
from assayer.runner import load_cases

from evals.cassette import Cassette, cassette_path, replay_session
from evals.dataset import load_split
from evals.draft_precedents import DRAFTS_FILE, SPECS, _clean


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(self, *args, **kwargs):
        raise AssertionError("replay opened a network connection")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)


def _drafts() -> list[dict]:
    files = [
        DRAFTS_FILE.parent.parent / split / DRAFTS_FILE.name for split in ("tuning", "validation")
    ]
    return [c for f in files for c in json.loads(f.read_text(encoding="utf-8"))]


def _first_call(case: dict) -> tuple[str, dict]:
    entry = case["expected_tool_calls"][0]
    entry = entry["any_of"][0] if isinstance(entry, dict) and "any_of" in entry else entry
    if isinstance(entry, str):
        return entry, {}
    return entry["name"], entry.get("arguments", {})


def test_the_drafts_load_with_the_dataset_and_assayer_loaders():
    dataset = load_split("tuning")
    dataset.cases += load_split("validation").cases
    ids = {c["id"] for c in _drafts()}
    assert ids <= {case.id for case in dataset.cases}
    assert len(load_cases(_drafts()).cases) == len(ids)


def test_the_drafts_cover_every_kind_and_have_a_dated_cassette():
    ids = {c["id"] for c in _drafts()}
    for marker in ("-prec-", "-neg-", "-cov-"):
        assert any(marker in i for i in ids), marker
    for case_id in ids:
        assert Cassette.load(cassette_path(case_id)).recorded_on.year >= 2026
    assert ids <= {spec.id for spec in SPECS}


def test_negative_drafts_expect_that_nothing_was_found():
    negatives = [c for c in _drafts() if "-neg-" in c["id"]]
    assert negatives
    for case in negatives:
        assert "no Precedent" in case["expected_outcome"]
        assert case["reference_context_ids"] == []


async def test_the_first_expected_call_replays_without_a_cassette_miss():
    for case in _drafts():
        name, arguments = _first_call(case)
        async with replay_session(Cassette.load(cassette_path(case["id"]))) as session:
            result = await session.client.call_tool(name, arguments, raise_on_error=False)
            assert not result.is_error, case["id"]
            assert session.misses == 0, case["id"]


async def test_reference_ids_are_in_the_recorded_search():
    for case in _drafts():
        if not case["reference_context_ids"]:
            continue
        name, arguments = _first_call(case)
        async with replay_session(Cassette.load(cassette_path(case["id"]))) as session:
            result = await session.client.call_tool(name, arguments)
        returned = {item["id"] for item in result.structured_content["items"]}
        assert set(case["reference_context_ids"]) <= returned, case["id"]


def test_a_thesis_that_is_unknown_or_redacted_is_not_an_expected_fact():
    assert _clean("não informado") is None
    assert _clean("O Código de [NOME] é aplicável") is None
    assert _clean("Texto  com   espaços") == "Texto com espaços"
