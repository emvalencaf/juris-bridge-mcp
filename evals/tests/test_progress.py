"""The resumable progress store: finished units and their outputs survive a stop."""

import json

import pytest

from evals.llm import AllKeysExhausted
from evals.progress import Progress, ProgressError, case_of, unit_key


def test_a_unit_key_joins_the_case_id_and_the_repetition():
    assert unit_key("lookup-1", 2) == "lookup-1#2"


def test_a_new_store_has_nothing_done(tmp_path):
    progress = Progress(tmp_path / "p.json")

    assert not progress.is_done("a#0")
    assert len(progress) == 0


def test_a_recorded_unit_is_done_and_returns_its_output(tmp_path):
    progress = Progress(tmp_path / "p.json")

    progress.record("a#0", {"answer": "x"})

    assert progress.is_done("a#0")
    assert progress.get("a#0") == {"answer": "x"}


def test_records_are_saved_at_once_and_reloaded(tmp_path):
    path = tmp_path / "sub" / "p.json"
    Progress(path).record("a#0", {"n": 1})

    reopened = Progress(path)

    assert reopened.is_done("a#0")
    assert reopened.get("a#0") == {"n": 1}
    assert json.loads(path.read_text())["units"] == {"a#0": {"n": 1}}


def test_run_calls_the_work_once_and_then_replays_its_output(tmp_path):
    progress = Progress(tmp_path / "p.json")
    calls = []

    def work():
        calls.append(1)
        return {"v": len(calls)}

    first = progress.run("a#0", work)
    again = Progress(tmp_path / "p.json").run("a#0", work)

    assert first == again == {"v": 1}
    assert calls == [1]


def test_a_stopped_unit_is_not_recorded_and_finished_ones_stay(tmp_path):
    progress = Progress(tmp_path / "p.json")
    progress.run("a#0", lambda: "ok")

    def exhausted():
        raise AllKeysExhausted("no key left")

    with pytest.raises(AllKeysExhausted):
        progress.run("a#1", exhausted)

    resumed = Progress(tmp_path / "p.json")
    assert resumed.is_done("a#0")
    assert not resumed.is_done("a#1")


def test_an_output_that_is_not_json_is_refused_and_not_recorded(tmp_path):
    progress = Progress(tmp_path / "p.json")

    with pytest.raises(ProgressError):
        progress.record("a#0", {"bad": object()})

    assert not progress.is_done("a#0")


def test_an_unreadable_file_is_a_clear_error(tmp_path):
    path = tmp_path / "p.json"
    path.write_text("{not json")

    with pytest.raises(ProgressError, match=r"p\.json"):
        Progress(path)


def test_clear_forgets_everything_and_removes_the_file(tmp_path):
    path = tmp_path / "p.json"
    progress = Progress(path)
    progress.record("a#0", 1)

    progress.clear()

    assert len(progress) == 0
    assert not path.exists()


def test_the_case_id_is_read_back_from_a_unit_key():
    assert case_of(unit_key("draft-pub#x", 2)) == "draft-pub#x"
