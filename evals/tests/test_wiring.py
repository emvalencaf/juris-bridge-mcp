"""Wiring check of the evaluation: an empty Dataset becomes an empty Experiment."""

from evals.__main__ import main
from evals.dataset import load_split


def test_an_empty_split_loads_as_an_empty_dataset(tmp_path):
    dataset = load_split("tuning", root=tmp_path)

    assert dataset.name == "tuning"
    assert dataset.cases == []


def test_split_cases_are_read_from_its_json_files(tmp_path):
    (tmp_path / "tuning").mkdir()
    (tmp_path / "tuning" / "lookups.json").write_text('[{"input": "q", "id": "a"}]')

    assert [c.id for c in load_split("tuning", root=tmp_path).cases] == ["a"]


def test_main_prints_an_empty_experiment(capsys):
    assert main(["run", "--split", "drafts"]) == 0

    out = capsys.readouterr().out
    assert "Experiment" in out
    assert "cases: 0" in out
