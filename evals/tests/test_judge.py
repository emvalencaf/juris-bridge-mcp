"""The rubric judge: parsing, repetition, spread, the uncalibrated mark and the opt-in flag."""

import json
import socket

import pytest
from assayer.metrics import Metric
from assayer.models import Case, Dataset, Step, Trajectory
from assayer.registries import Registry

from evals.__main__ import main
from evals.dataset import load_split
from evals.judge import (
    JUDGE,
    LLMClientJudge,
    format_judge_line,
    load_calibration,
    make_rubric_judge,
    parse_judgment,
    register_judge,
)
from evals.llm import ChatResult, ScriptedLLMClient, Usage
from evals.run import format_experiment, run_eval


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(self, *args, **kwargs):
        raise AssertionError("the run opened a network connection")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)


def reply(correctness="correct", grounding="grounded", reason="ok") -> ChatResult:
    text = json.dumps({"correctness": correctness, "grounding": grounding, "reason": reason})
    return ChatResult(text=text, usage=Usage(30, 10))


def agent_answer() -> ChatResult:
    return ChatResult(text="done", usage=Usage(20, 7))


def trajectory() -> Trajectory:
    return Trajectory(
        steps=[Step(kind="tool", name="get_precedent", input={"id": "x"}, output="TESE: abc")],
        final_output="A tese é abc.",
        case_id="c1",
    )


CASE = Case(id="c1", input="Qual a tese?", expected_outcome="States the thesis abc.")


def run_metric(script, **kwargs):
    llm = ScriptedLLMClient(script)
    metric = make_rubric_judge(LLMClientJudge(llm), calibration=None, **kwargs)
    return llm, metric.evaluate(trajectory(), CASE)


def test_parse_reads_the_rubric_labels():
    v = parse_judgment('{"correctness": "Incorrect", "grounding": "misgrounded", "reason": "r"}')

    assert (v.correctness, v.grounding, v.reason) == ("incorrect", "misgrounded", "r")


@pytest.mark.parametrize(
    "text",
    ["", "not json", "[1, 2]", '{"correctness": "maybe", "grounding": 3}', "{"],
)
def test_invalid_output_is_unknown_never_a_crash(text):
    v = parse_judgment(text)

    assert (v.correctness, v.grounding) == ("unknown", "unknown")


def test_one_valid_field_survives_when_the_other_is_missing():
    v = parse_judgment('{"correctness": "correct"}')

    assert (v.correctness, v.grounding) == ("correct", "unknown")


def test_json_inside_a_code_fence_or_prose_is_read():
    text = 'Here:\n```json\n{"correctness": "refusal", "grounding": "ungrounded"}\n```'

    v = parse_judgment(text)

    assert (v.correctness, v.grounding) == ("refusal", "ungrounded")


def test_the_model_may_answer_unknown():
    v = parse_judgment('{"correctness": "unknown", "grounding": "Unknown"}')

    assert (v.correctness, v.grounding) == ("unknown", "unknown")


def test_each_judgment_is_repeated_three_times_by_default_and_the_spread_is_kept():
    llm, outcome = run_metric([reply(), reply(), reply("incorrect", "misgrounded")])

    assert len(llm.calls) == 3
    (score,) = outcome.scores
    meta = score.metadata
    assert score.name == JUDGE
    assert meta["correctness"] == "correct" and meta["grounding"] == "grounded"
    assert meta["counts"]["correctness"] == {"correct": 2, "incorrect": 1}
    assert meta["counts"]["grounding"] == {"grounded": 2, "misgrounded": 1}
    assert meta["agreement"]["correctness"] == pytest.approx(2 / 3)
    assert len(meta["repetitions"]) == 3
    assert score.value == pytest.approx(2 / 3)
    assert outcome.judge_calls == 3


def test_repetitions_are_configurable():
    llm, outcome = run_metric([reply(), reply()], repetitions=2)

    assert len(llm.calls) == 2
    assert outcome.scores[0].metadata["agreement"]["correctness"] == 1.0


def test_a_tie_makes_the_verdict_unknown_and_garbage_counts_as_unknown():
    _, outcome = run_metric([reply("correct"), reply("incorrect"), ChatResult(text="???")])

    (score,) = outcome.scores
    assert score.metadata["correctness"] == "unknown"
    assert score.metadata["counts"]["correctness"]["unknown"] == 1
    assert score.value == pytest.approx(1 / 3)
    assert not outcome.failures


def test_the_prompt_carries_question_expected_outcome_tool_results_and_answer():
    llm, _ = run_metric([reply()] * 3)

    messages, _tools, system = llm.calls[0]
    text = (system or "") + "\n" + messages[0].text
    for part in ("Qual a tese?", "States the thesis abc.", "TESE: abc", "A tese é abc."):
        assert part in text


def test_results_are_uncalibrated_without_a_calibration_record(tmp_path):
    assert load_calibration(tmp_path / "calibration.json") is None
    _, outcome = run_metric([reply()] * 3)

    assert outcome.scores[0].metadata["uncalibrated"] is True


def test_a_calibration_record_clears_the_mark(tmp_path):
    path = tmp_path / "calibration.json"
    path.write_text('{"agreement": 0.9}')
    record = load_calibration(path)
    metric = make_rubric_judge(LLMClientJudge(ScriptedLLMClient([reply()] * 3)), calibration=record)

    meta = metric.evaluate(trajectory(), CASE).scores[0].metadata

    assert record == {"agreement": 0.9}
    assert meta["uncalibrated"] is False


def test_a_broken_calibration_file_counts_as_uncalibrated(tmp_path):
    path = tmp_path / "calibration.json"
    path.write_text("{")

    assert load_calibration(path) is None


def test_the_judge_is_a_registered_metric():
    registry = Registry()

    register_judge(registry, ScriptedLLMClient([]))

    assert isinstance(registry.get(JUDGE), Metric)


def seed_case(case_id="seed-coverage") -> Dataset:
    return Dataset("seed", [c for c in load_split("seed").cases if c.id == case_id])


def test_a_run_without_the_flag_spends_no_judge_call():
    experiment = run_eval(seed_case(), ScriptedLLMClient([agent_answer()]))

    assert not [s for s in experiment.scores if s.name == JUDGE]
    assert "UNCALIBRATED" not in format_experiment(experiment)


def test_a_run_with_a_judge_reports_the_verdict_spread_marked_uncalibrated():
    judge_llm = ScriptedLLMClient([reply(), reply(), reply("incorrect", "grounded")])

    experiment = run_eval(seed_case(), ScriptedLLMClient([agent_answer()]), judge=judge_llm)
    text = format_experiment(experiment)

    assert len(judge_llm.calls) == 3
    assert "judge: correct" in text and "UNCALIBRATED" in text
    assert "correct 2" in text and "incorrect 1" in text


def test_format_judge_line_names_agreement():
    _, outcome = run_metric([reply()] * 3)

    line = format_judge_line(outcome.scores[0])

    assert "agreement 1.00" in line and "UNCALIBRATED" in line


def test_the_cli_flag_judges_with_the_judge_client(capsys, tmp_path):
    cases = len(load_split("seed").cases)
    agent = ScriptedLLMClient([agent_answer()] * cases)
    judge_llm = ScriptedLLMClient([reply()] * 3 * cases)

    args = ["run", "--split", "seed", "--repetitions", "1", "--judge"]
    assert main(args, llm=agent, judge_llm=judge_llm, results_dir=tmp_path) == 0

    assert len(judge_llm.calls) == 3 * cases
    assert "UNCALIBRATED" in capsys.readouterr().out


def test_the_cli_without_the_flag_never_touches_the_judge_client(capsys, tmp_path):
    cases = len(load_split("seed").cases)
    judge_llm = ScriptedLLMClient([])

    main(
        ["run", "--split", "seed", "--repetitions", "1"],
        llm=ScriptedLLMClient([agent_answer()] * cases),
        judge_llm=judge_llm,
        results_dir=tmp_path,
    )

    assert judge_llm.calls == []
