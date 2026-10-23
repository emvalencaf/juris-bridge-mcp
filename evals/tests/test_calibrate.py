"""Calibrating the judge: label export, agreement, the calibration record and the un-marking."""

import json

import pytest
from assayer.models import Case, Experiment, Step, Trajectory

from evals.__main__ import main
from evals.calibrate import kappa, sample_ids
from evals.judge import format_judge_line, load_calibration
from evals.llm import ChatResult, ScriptedLLMClient, Usage
from evals.report import format_report
from evals.store import save_run


def reply(correctness="correct", grounding="grounded") -> ChatResult:
    text = json.dumps({"correctness": correctness, "grounding": grounding, "reason": "SECRET"})
    return ChatResult(text=text, usage=Usage(1, 1))


def experiment(cases=3, reps=2) -> Experiment:
    trajectories = [
        Trajectory(
            steps=[Step(kind="tool", name="search", input={}, output=f"result {c}")],
            final_output=f"answer {c}.{r}",
            case_id=f"case{c}",
        )
        for r in range(reps)
        for c in range(cases)
    ]
    return Experiment(
        name="tuning",
        trajectories=trajectories,
        cases=[
            Case(id=f"case{c}", input=f"question {c}", expected_outcome=f"outcome {c}")
            for c in range(cases)
        ],
    )


@pytest.fixture
def saved(tmp_path):
    path = save_run(experiment(), {}, root=tmp_path)
    return path.stem


def export(saved, tmp_path, *extra):
    out = tmp_path / "labels.json"
    assert (
        main(["calibrate", "export", saved, *extra, "--out", str(out)], results_dir=tmp_path) == 0
    )
    return json.loads(out.read_text())


def label(data, correctness, grounding, upto=None):
    for item in data["items"][:upto]:
        item["correctness"], item["grounding"] = correctness, grounding


def test_export_lists_the_answers_with_context_and_empty_labels(saved, tmp_path):
    data = export(saved, tmp_path, "--n", "4")

    assert len(data["items"]) == 4
    first = data["items"][0]
    assert first["question"] == "question 0" and first["expected_outcome"] == "outcome 0"
    assert "result 0" in first["context"] and first["answer"].startswith("answer 0")
    assert first["correctness"] == "" and first["grounding"] == ""
    assert len({i["id"] for i in data["items"]}) == 4


def test_export_never_leaks_the_judge_verdict(tmp_path):
    exp = experiment(cases=1, reps=1)
    exp.scores = []
    path = save_run(exp, {}, root=tmp_path)
    from assayer.models import Score

    exp.scores = [
        Score(
            name="judge",
            target_id="case0",
            value=1.0,
            metadata={"correctness": "correct", "reason": "SECRET"},
            comment="SECRET",
        )
    ]
    path = save_run(exp, {}, root=tmp_path)
    out = tmp_path / "labels.json"
    main(["calibrate", "export", path.stem, "--out", str(out)], results_dir=tmp_path)

    text = out.read_text()
    assert "SECRET" not in text and "uncalibrated" not in text and '"judge"' not in text


def test_sampling_is_deterministic_and_spread_across_cases():
    exp = experiment(cases=3, reps=4)

    ids = sample_ids(exp, 5)

    assert ids == sample_ids(exp, 5)
    assert [i.split("#")[0] for i in ids[:3]] == ["case0", "case1", "case2"]
    assert len(sample_ids(exp, 100)) == 12


def test_kappa():
    assert kappa([("a", "a"), ("b", "b")]) == 1.0
    assert kappa([("a", "b"), ("b", "a")]) == -1.0
    assert kappa([]) is None


def test_score_measures_agreement_and_writes_the_record(saved, tmp_path, capsys):
    data = export(saved, tmp_path, "--n", "4")
    label(data, "correct", "grounded", 3)
    data["items"][3]["correctness"] = "incorrect"  # grounding left unlabeled
    (tmp_path / "labels.json").write_text(json.dumps(data))
    client = ScriptedLLMClient([reply()] * 3 + [reply("correct", "ungrounded")])

    code = main(
        ["calibrate", "score", saved, str(tmp_path / "labels.json")],
        calibration_llm=client,
        results_dir=tmp_path,
    )

    record = load_calibration(tmp_path / "calibration.json")
    assert code == 0 and record["measured"] is True and record["labeled"] == 4
    assert record["correctness"]["n"] == 4 and record["correctness"]["agreement"] == 0.75
    assert record["grounding"]["n"] == 3 and record["grounding"]["agreement"] == 1.0
    assert record["joint"]["n"] == 3 and record["joint"]["agreement"] == 1.0
    assert "correctness: agreement 0.75 over 4" in capsys.readouterr().out


def test_unlabeled_items_are_ignored_and_counted(saved, tmp_path):
    data = export(saved, tmp_path, "--n", "4")
    label(data, "refusal", "unknown", 1)
    (tmp_path / "labels.json").write_text(json.dumps(data))

    main(
        ["calibrate", "score", saved, str(tmp_path / "labels.json")],
        calibration_llm=ScriptedLLMClient([reply("refusal", "unknown")]),
        results_dir=tmp_path,
    )

    record = load_calibration(tmp_path / "calibration.json")
    assert record["labeled"] == 1 and record["unlabeled"] == 3
    assert record["joint"]["agreement"] == 1.0


def test_nothing_labelled_writes_no_record(saved, tmp_path, capsys):
    export(saved, tmp_path)

    code = main(
        ["calibrate", "score", saved, str(tmp_path / "labels.json")],
        calibration_llm=ScriptedLLMClient([]),
        results_dir=tmp_path,
    )

    assert code == 1 and "nothing to measure" in capsys.readouterr().out
    assert load_calibration(tmp_path / "calibration.json") is None


def test_an_invalid_label_is_rejected(saved, tmp_path, capsys):
    data = export(saved, tmp_path)
    data["items"][0]["correctness"] = "maybe"
    (tmp_path / "labels.json").write_text(json.dumps(data))

    code = main(
        ["calibrate", "score", saved, str(tmp_path / "labels.json")],
        calibration_llm=ScriptedLLMClient([]),
        results_dir=tmp_path,
    )

    assert code == 1 and "maybe" in capsys.readouterr().out


def test_the_mark_drops_only_with_a_measured_record():
    from assayer.models import Score

    score = Score(
        name="judge",
        target_id="c",
        value=1.0,
        metadata={
            "correctness": "correct",
            "grounding": "grounded",
            "counts": {"correctness": {"correct": 3}, "grounding": {"grounded": 3}},
            "agreement": {"correctness": 1.0, "grounding": 1.0},
            "uncalibrated": True,
        },
    )
    exp = Experiment(name="x", scores=[score])

    assert "UNCALIBRATED" in format_judge_line(score)
    assert "UNCALIBRATED" in format_judge_line(score, {"agreement": 0.9})
    assert "UNCALIBRATED" not in format_judge_line(score, {"measured": True})
    assert "UNCALIBRATED" in format_report(exp, calibration=None)
    record = {
        "measured": True,
        "labeled": 2,
        "unlabeled": 0,
        "correctness": {"n": 2, "agreement": 0.5, "kappa": 0.0},
    }
    report = format_report(exp, calibration=record)
    assert "UNCALIBRATED" not in report and "correctness: agreement 0.50 over 2" in report
