"""The draft Publication Eval cases: they load and replay against their Cassettes; no network."""

import re
import socket

import pytest

from evals.cassette import Cassette, cassette_path, replay_session
from evals.dataset import load_split
from evals.draft_publications import DRAFTS_PATH, SEARCH_SPECS, SearchSpec, draft_search

CPF = re.compile(r"(?<!\d)\d{3}\.\d{3}\.\d{3}-\d{2}(?!\d)")
CNPJ = re.compile(r"(?<!\d)\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}(?!\d)")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(self, *args, **kwargs):
        raise AssertionError("a test opened a network connection")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)


def publication_drafts():
    return [c for c in load_split("drafts").cases if c.id.startswith("draft-pub-")]


def test_drafts_exist_and_are_about_twenty():
    assert len(publication_drafts()) >= 18


def test_every_draft_declares_its_kind_and_its_expected_values():
    for case in publication_drafts():
        assert case.expected_state["kind"] in {"lookup", "search"}
        assert case.reference_context_ids
        assert case.expected_tool_calls
        assert cassette_path(case.id).exists()


@pytest.mark.parametrize("case", publication_drafts(), ids=lambda c: c.id)
async def test_the_first_expected_call_replays_without_a_miss(case):
    call = case.expected_tool_calls[0]
    cassette = Cassette.load(cassette_path(case.id))
    arguments = (
        {**call["arguments"], "limit": 5} if "query" in call["arguments"] else call["arguments"]
    )
    async with replay_session(cassette) as session:
        result = await session.client.call_tool(call["name"], arguments, raise_on_error=False)

    assert not result.is_error
    assert session.misses == 0
    cited = {item["cnj_number"] for item in result.structured_content["items"]}
    assert set(case.reference_context_ids) <= cited


@pytest.mark.parametrize("case", publication_drafts(), ids=lambda c: c.id)
def test_cassettes_hold_no_cpf_or_cnpj(case):
    text = cassette_path(case.id).read_text(encoding="utf-8")

    assert not CPF.search(text)
    assert not CNPJ.search(text)


def test_the_drafts_file_is_the_one_the_loader_reads():
    assert DRAFTS_PATH.parent.name == "drafts"
    assert len(SEARCH_SPECS) >= 9


def test_a_search_draft_copies_its_expected_values_from_the_response():
    spec = SearchSpec("x", "tjsp", "recurso")
    result = {
        "complete": True,
        "items": [
            {
                "cnj_number": "1-1",
                "published_on": "2026-10-20",
                "kind": "acordao",
                "document_type": "Acórdão",
            },
            {
                "cnj_number": "1-1",
                "published_on": "2026-10-19",
                "kind": "acordao",
                "document_type": "Acórdão",
            },
        ],
    }

    draft = draft_search(spec, result)

    assert draft["reference_context_ids"] == ["1-1"]
    assert "2 Publication(s)" in draft["expected_outcome"]
    assert "2026-10-19, 2026-10-20" in draft["expected_outcome"]
