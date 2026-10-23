"""`python -m evals run` end to end: seed Eval cases, seed Cassettes, a scripted model."""

import asyncio
import json
import socket
from datetime import date
from pathlib import Path

import pytest
from assayer.models import Dataset

from evals.__main__ import main
from evals.cassette import Cassette, cassette_path
from evals.dataset import load_split
from evals.llm import ChatResult, ScriptedLLMClient, ToolCall, Usage
from evals.run import format_experiment, run_eval
from evals.seed import SEED_CALLS, write_seed_cassettes


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(self, *args, **kwargs):
        raise AssertionError("the run opened a network connection")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)


def calls(*items: tuple[str, dict]) -> ChatResult:
    return ChatResult(
        tool_calls=tuple(ToolCall(n, a) for n, a in items), usage=Usage(10, 5), key_alias="key-1"
    )


def answer(text: str = "done") -> ChatResult:
    return ChatResult(text=text, usage=Usage(20, 7), key_alias="key-1")


def score_of(experiment, case_id, name="tool_use"):
    (found,) = [s for s in experiment.scores if s.name == name and s.target_id == case_id]
    return found


def test_the_seed_cases_load_and_each_has_a_seed_cassette():
    dataset = load_split("seed")

    assert {c.id for c in dataset.cases} == set(SEED_CALLS)
    for case in dataset.cases:
        assert case.expected_tool_calls
        assert cassette_path(case.id).exists()
        assert Cassette.load(cassette_path(case.id)).recorded_on <= date.today()


def test_the_seed_cassettes_are_reproducible_from_the_fixtures(tmp_path):
    asyncio.run(write_seed_cassettes(tmp_path, date(2026, 10, 22)))

    for case_id in SEED_CALLS:
        mine = Cassette.load(cassette_path(case_id, root=tmp_path))
        shipped = Cassette.load(cassette_path(case_id))
        assert mine.entries == shipped.entries


def test_the_expected_route_scores_one_and_leaves_a_trajectory_per_case():
    dataset = load_split("seed")
    scripts = {
        "seed-coverage": [calls(("list_coverage", {})), answer()],
        "seed-precedent-rg-1002": [
            calls(("search_precedents", {"number": "1002", "kind": "RG", "court": "stf"})),
            answer(),
        ],
        "seed-publications-by-cnj": [
            calls(
                (
                    "search_publications",
                    {
                        "cnj_number": "1234567-76.2025.8.26.0100",
                        "court": "tjsp",
                        "date_from": "2026-10-15",
                        "date_to": "2026-10-15",
                    },
                )
            ),
            answer(),
        ],
    }
    llm = ScriptedLLMClient([item for case in dataset.cases for item in scripts[case.id]])

    experiment = run_eval(dataset, llm)

    assert len(experiment.trajectories) == len(dataset.cases)
    assert {t.case_id for t in experiment.trajectories} == set(SEED_CALLS)
    for case in dataset.cases:
        assert score_of(experiment, case.id).value == 1.0
    assert not experiment.failures
    assert all(t.final_state["cassette_misses"] == 0 for t in experiment.trajectories)


def test_an_alternative_valid_route_is_not_marked_wrong():
    dataset = Dataset(
        "seed", [c for c in load_split("seed").cases if c.id == "seed-precedent-rg-1002"]
    )
    llm = ScriptedLLMClient(
        [
            calls(("list_coverage", {})),
            calls(("search_precedents", {"query": "tema 1002", "court": "stf"})),
            calls(("get_precedent", {"id": "stf-rg-1002"})),
            answer(),
        ]
    )

    experiment = run_eval(dataset, llm)

    assert score_of(experiment, "seed-precedent-rg-1002").value == 1.0


def test_a_wrong_tool_scores_low_and_the_run_still_finishes():
    dataset = Dataset("seed", [c for c in load_split("seed").cases if c.id == "seed-coverage"])
    llm = ScriptedLLMClient([calls(("search_precedents", {"query": "x"})), answer()])

    experiment = run_eval(dataset, llm)

    assert score_of(experiment, "seed-coverage").value == 0.0


def test_a_case_without_a_cassette_is_recorded_as_an_error_not_a_crash(tmp_path):
    dataset = Dataset("seed", [c for c in load_split("seed").cases if c.id == "seed-coverage"])

    experiment = run_eval(dataset, ScriptedLLMClient([]), cassettes_root=tmp_path)

    step = experiment.trajectories[0].steps[0]
    assert "seed-coverage" in step.error and "FileNotFoundError" in step.error


def test_the_report_lists_each_case_with_its_score_and_the_caveats():
    dataset = Dataset("seed", [c for c in load_split("seed").cases if c.id == "seed-coverage"])
    experiment = run_eval(dataset, ScriptedLLMClient([calls(("list_coverage", {})), answer()]))

    text = format_experiment(experiment)

    assert "seed-coverage" in text and "tool_use 1.00" in text
    assert "tokens 42" in text and "calls 1" in text and "cassette misses 0" in text


def test_main_runs_the_split_with_an_injected_client(capsys, tmp_path):
    dataset_ids = [c.id for c in load_split("seed").cases]
    script = [item for _ in dataset_ids for item in (calls(("list_coverage", {})), answer())]

    code = main(
        ["run", "--split", "seed", "--repetitions", "1"],
        llm=ScriptedLLMClient(script),
        results_dir=tmp_path,
    )

    out = capsys.readouterr().out
    assert code == 0
    assert f"cases: {len(dataset_ids)}" in out
    assert "seed-coverage" in out and "tool_use" in out


def test_the_empty_split_still_works_without_a_model(capsys):
    assert main([]) == 0
    assert "cases: 0" in capsys.readouterr().out


def test_cases_are_plain_json_in_assayers_loader_format():
    root = Path(__file__).parents[1] / "cases" / "seed"
    for path in root.glob("*.json"):
        for entry in json.loads(path.read_text(encoding="utf-8")):
            assert isinstance(entry["input"], str) and entry["id"]
            assert set(entry) <= {
                "id",
                "input",
                "expected_tool_calls",
                "reference_context_ids",
                "expected_outcome",
                "expected_state",
            }
