"""Repetitions, consistency by case kind, efficiency, the report, saving and comparing runs."""

import json
import socket
from datetime import datetime

import pytest
from assayer.models import Dataset

from evals.__main__ import main
from evals.compare import format_comparison
from evals.consistency import case_kind, consistency, efficiency
from evals.dataset import load_split
from evals.llm import AllKeysExhausted, ChatResult, ScriptedLLMClient, ToolCall, Usage
from evals.progress import Progress, unit_key
from evals.report import format_report, model_family
from evals.run import RunStopped, run_eval
from evals.store import StoreError, load_run, save_run


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(self, *args, **kwargs):
        raise AssertionError("the run opened a network connection")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)


def calls(*items):
    return ChatResult(
        tool_calls=tuple(ToolCall(n, a) for n, a in items), usage=Usage(10, 5), key_alias="key-1"
    )


def answer():
    return ChatResult(text="done", usage=Usage(20, 7), key_alias="key-1")


GOOD = [calls(("list_coverage", {})), answer()]
BAD = [calls(("search_precedents", {"query": "x"})), answer()]


def coverage_dataset(kind=None):
    (case,) = [c for c in load_split("seed").cases if c.id == "seed-coverage"]
    if kind:
        case.expected_state = {"kind": kind}
    return Dataset("seed", [case])


def run(script, kind=None, repetitions=3, **kwargs):
    return run_eval(
        coverage_dataset(kind),
        ScriptedLLMClient([i for part in script for i in part]),
        repetitions=repetitions,
        **kwargs,
    )


def test_each_eval_case_is_repeated_and_kept_as_separate_trajectories():
    experiment = run([GOOD] * 3)

    assert [t.repetition for t in experiment.trajectories] == [0, 1, 2]
    assert {t.case_id for t in experiment.trajectories} == {"seed-coverage"}
    assert len([s for s in experiment.scores if s.name == "tool_use"]) == 3


def test_a_lookup_must_pass_every_time():
    (row,) = consistency(run([GOOD, GOOD, BAD], kind="lookup"))

    assert (row.kind, row.passes, row.runs, row.passed) == ("lookup", 2, 3, False)
    assert row.rule == "all-pass"


def test_an_open_search_needs_one_pass():
    (row,) = consistency(run([BAD, GOOD, BAD], kind="search"))

    assert (row.kind, row.passes, row.passed) == ("search", 1, True)
    assert row.rule == "at-least-one"


def test_an_open_search_that_never_passes_fails():
    (row,) = consistency(run([BAD, BAD, BAD], kind="search"))

    assert not row.passed


def test_the_kind_defaults_to_the_strict_rule_and_rejects_unknown_ones():
    (case,) = coverage_dataset().cases
    assert case_kind(case) == "lookup"
    case.expected_state = {"kind": "browse"}
    with pytest.raises(ValueError, match="kind must be one of"):
        case_kind(case)


def test_efficiency_reports_calls_tokens_and_tool_errors_per_case():
    experiment = run([GOOD, GOOD, GOOD], repetitions=3)

    (row,) = efficiency(experiment)

    assert (row.runs, row.calls, row.tokens, row.errors) == (3, 1.0, 42.0, 0.0)
    assert row.repeated_invalid == []


def bad_arguments(arguments):
    return calls(("search_publications", arguments))


def test_the_same_invalid_arguments_twice_are_flagged():
    wrong = {"court": "nowhere"}
    experiment = run([[bad_arguments(wrong), bad_arguments(wrong), answer()], BAD], repetitions=2)

    (row,) = efficiency(experiment)

    assert row.errors > 0
    assert [(r.tool, r.count) for r in row.repeated_invalid] == [("search_publications", 2)]
    assert "FLAG seed-coverage: search_publications failed 2x" in format_report(experiment)


def test_different_invalid_arguments_are_not_flagged():
    experiment = run(
        [[bad_arguments({"court": "a"}), bad_arguments({"court": "b"}), answer()]], repetitions=1
    )

    (row,) = efficiency(experiment)

    assert row.errors > 0 and row.repeated_invalid == []


def test_the_report_has_the_sections_and_states_its_limits():
    text = format_report(
        run([GOOD, GOOD, BAD]),
        {"agent_model": "gemini-2.5-flash", "judge_model": "gemini-2.5-pro"},
    )

    assert "Consistency" in text and "seed-coverage: 2/3 runs | lookup (all-pass) | FAIL" in text
    assert "Efficiency" in text and "calls 1.0" in text
    assert "Name redaction" in text and "small model" in text
    assert "Cassette misses in this run:" in text
    assert "share the 'gemini' family" in text


def test_the_report_says_when_agent_and_judge_differ_and_counts_cassette_misses():
    experiment = run([GOOD], repetitions=1)
    experiment.trajectories[0].final_state = {"cassette_misses": 4}

    text = format_report(experiment, {"agent_model": "gemini-x", "judge_model": "gpt-4o"})

    assert "different families" in text and "misses in this run: 4" in text
    assert model_family("models/Gemini-2.5-flash") == "gemini"


def test_a_section_can_be_added_to_the_report():
    text = format_report(run([GOOD], repetitions=1), sections=[lambda e, m: ["Citations", "  x"]])

    assert "Citations\n  x" in text and "Limits" in text


def test_the_run_is_saved_with_a_timestamped_name_and_loads_back(tmp_path):
    experiment = run([GOOD, BAD, GOOD])
    meta = {"split": "seed", "repetitions": 3}

    path = save_run(experiment, meta, root=tmp_path, now=datetime(2026, 10, 22, 9, 30, 5))

    assert path.name == "seed-20261022-093005.json"
    loaded, loaded_meta = load_run(path)
    assert loaded_meta["split"] == "seed" and loaded_meta["saved_at"].startswith("2026-10-22")
    assert [(t.case_id, t.repetition) for t in loaded.trajectories] == [
        (t.case_id, t.repetition) for t in experiment.trajectories
    ]
    assert loaded.scores == experiment.scores and loaded.cases == experiment.cases
    assert loaded.trajectories[0].steps == experiment.trajectories[0].steps
    assert consistency(loaded) == consistency(experiment)
    assert load_run("seed-20261022-093005", root=tmp_path)[0].name == "seed"


def test_the_key_aliases_survive_a_save_and_load_and_never_the_key(tmp_path):
    experiment = run([GOOD])
    experiment.trajectories[0].final_state = {"cassette_misses": 0, "key_aliases": ["key-1"]}

    path = save_run(experiment, {}, root=tmp_path)

    loaded, _ = load_run(path)
    assert loaded.trajectories[0].final_state["key_aliases"] == ["key-1"]


def test_a_missing_or_broken_run_is_a_store_error(tmp_path):
    with pytest.raises(StoreError):
        load_run("nope", root=tmp_path)
    (tmp_path / "bad.json").write_text("{")
    with pytest.raises(StoreError):
        load_run("bad", root=tmp_path)


def test_results_are_kept_out_of_version_control():
    from pathlib import Path

    ignore = (Path(__file__).parents[2] / ".gitignore").read_text()
    assert "evals/results/" in ignore


def test_two_runs_compare_per_metric_tokens_and_calls():
    a = run([GOOD, GOOD, GOOD])
    b = run([BAD, BAD, BAD])

    text = format_comparison(a, b, "a", "b")

    assert "b minus a" in text and "tool_use: -1.00" in text
    assert "tokens per Eval case: +0" in text
    assert "tool calls per Eval case: +0.00" in text
    assert "cases passing by their rule: -1.00" in text


def test_main_saves_the_run_and_compares_two_saved_runs(tmp_path, capsys):
    for _ in range(2):
        argv = ["run", "--split", "seed", "--repetitions", "1"]
        assert main(argv, llm=_seed_llm(), results_dir=tmp_path) == 0
    saved = sorted(p.name for p in tmp_path.glob("seed-*.json"))
    assert len(saved) == 2 and not (tmp_path / "progress-seed.json").exists()
    capsys.readouterr()

    assert main(["compare", saved[0], saved[-1]], results_dir=tmp_path) == 0
    assert "Comparison" in capsys.readouterr().out
    assert main(["compare", "missing", saved[0]], results_dir=tmp_path) == 1


def _seed_llm():
    scripts = {
        "seed-coverage": GOOD,
        "seed-precedent-rg-1002": [calls(("list_coverage", {})), answer()],
        "seed-publications-by-cnj": [calls(("list_coverage", {})), answer()],
    }
    return ScriptedLLMClient([i for c in load_split("seed").cases for i in scripts[c.id]])


def test_exhausted_keys_stop_the_run_with_progress_saved_and_resume_skips_it(tmp_path):
    progress = Progress(tmp_path / "progress.json")
    dataset = coverage_dataset()
    llm = ScriptedLLMClient([*GOOD, *GOOD, AllKeysExhausted("out")])

    with pytest.raises(RunStopped, match="resume"):
        run_eval(dataset, llm, repetitions=3, progress=progress)

    assert progress.is_done(unit_key("seed-coverage", 0))
    assert progress.is_done(unit_key("seed-coverage", 1))
    assert not progress.is_done(unit_key("seed-coverage", 2))

    resumed = ScriptedLLMClient(GOOD)  # one run only: the finished two are not repeated
    experiment = run_eval(
        dataset, resumed, repetitions=3, progress=Progress(tmp_path / "progress.json")
    )

    assert len(experiment.trajectories) == 3
    assert len(resumed.calls) == 2  # one model call, then the answer
    assert not experiment.failures
    json.loads((tmp_path / "progress.json").read_text())


def test_main_stops_cleanly_on_exhausted_keys(tmp_path, capsys):
    llm = ScriptedLLMClient([AllKeysExhausted("out")])

    code = main(["run", "--split", "seed", "--repetitions", "1"], llm=llm, results_dir=tmp_path)

    assert code == 1
    assert "Run stopped" in capsys.readouterr().out
    assert not list(tmp_path.glob("seed-*.json"))
