"""The rubric judge: a model grades each answer as correct / incorrect / refusal and as
grounded / misgrounded / ungrounded (the Stanford legal-AI rubric), or says "unknown".

`LLMClientJudge` adapts our `LLMClient` (on the judge model) to assayer's `Judge`, so the
metric is an ordinary assayer judge-based `Metric`. Each judgment is repeated
`DEFAULT_REPETITIONS` times and the spread (verdict counts, agreement) is kept on the Score.
Output that is not valid JSON or uses another label counts as "unknown", never a crash.

Results are UNCALIBRATED until a calibration record exists at `CALIBRATION_PATH`
(`evals/results/calibration.json`, written by the calibration ticket #105): `load_calibration`
returns it, or None when it is absent or unreadable.

Stored verdict (a Score's `metadata`, read by the calibration): `correctness` and `grounding`
(majority label; "unknown" on a tie), `counts` (per axis, label to repetitions), `agreement`
(per axis, share of repetitions on the majority label), `repetitions` (list of
`{correctness, grounding, reason}`), `uncalibrated`, `prompt` and `prompt_hash`. The Score's
value is the share of repetitions that were correct and grounded.
"""

import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from assayer.judges import Judge, JudgeResponse, Prompt, call_judge
from assayer.metrics import Detailed, Metric
from assayer.models import Case, Score, TokenUsage, Trajectory

from evals.llm import LLMClient, Message

JUDGE = "judge"
DEFAULT_REPETITIONS = 3
CORRECTNESS = ("correct", "incorrect", "refusal")
GROUNDING = ("grounded", "misgrounded", "ungrounded")
UNKNOWN = "unknown"
CALIBRATION_PATH = Path(__file__).parent / "results" / "calibration.json"

RUBRIC_PROMPT = Prompt(
    id="rubric",
    version="1",
    system=(
        "You are a strict, impartial evaluator of answers about Brazilian case law and court "
        "publications, given by an agent that used search tools. Judge only what you are given.\n"
        "Rate two things.\n"
        "correctness, against the expected outcome: 'correct' (the answer does what the "
        "expected outcome asks), 'incorrect' (it states something wrong or misses the point), "
        "'refusal' (it declines or says it cannot answer).\n"
        "grounding, against the tool results: 'grounded' (every claim is supported by the tool "
        "results), 'misgrounded' (it cites or relies on tool results that do not support the "
        "claim), 'ungrounded' (it states facts found in no tool result).\n"
        "If you cannot decide either one, answer 'unknown' for it; never guess.\n"
        'Reply with only a JSON object: {"correctness": "<correct|incorrect|refusal|unknown>", '
        '"grounding": "<grounded|misgrounded|ungrounded|unknown>", "reason": "<one or two '
        'sentences>"}.'
    ),
    user=(
        "Question:\n$input\n\n"
        "Expected outcome:\n$expected_outcome\n\n"
        "Tool results (the retrieved context):\n$context\n\n"
        "Agent's final answer:\n$output\n\n"
        "Give the JSON verdict."
    ),
)
_SCHEMA = {
    "type": "object",
    "properties": {
        "correctness": {"type": "string", "enum": [*CORRECTNESS, UNKNOWN]},
        "grounding": {"type": "string", "enum": [*GROUNDING, UNKNOWN]},
        "reason": {"type": "string"},
    },
    "required": ["correctness", "grounding", "reason"],
}


@dataclass(frozen=True)
class JudgeVerdict:
    """One judgment: a label per axis ("unknown" when undecided or unreadable)."""

    correctness: str = UNKNOWN
    grounding: str = UNKNOWN
    reason: str = ""


class LLMClientJudge:
    """An assayer `Judge` backed by an `LLMClient` (build it on the judge model)."""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def complete(
        self, messages: list[dict[str, str]], schema: dict[str, Any] | None = None
    ) -> JudgeResponse:
        """Send the messages (system ones become the system instruction); `schema` is ignored."""
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system") or None
        turns = [Message(role="user", text=m["content"]) for m in messages if m["role"] != "system"]
        result = self._llm.chat(turns, system=system)
        usage = TokenUsage(result.usage.input_tokens, result.usage.output_tokens, None)
        return JudgeResponse(text=result.text, usage=usage)


def _object(text: str) -> dict[str, Any]:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        value = json.loads(text[start : end + 1])
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def _label(value: Any, allowed: tuple[str, ...]) -> str:
    label = value.strip().casefold() if isinstance(value, str) else ""
    return label if label in allowed else UNKNOWN


def parse_judgment(text: str) -> JudgeVerdict:
    """Read one reply; anything unreadable or off-rubric becomes "unknown". Never raises."""
    data = _object(text or "")
    reason = data.get("reason")
    return JudgeVerdict(
        _label(data.get("correctness"), CORRECTNESS),
        _label(data.get("grounding"), GROUNDING),
        reason if isinstance(reason, str) else "",
    )


def load_calibration(path: Path = CALIBRATION_PATH) -> dict[str, Any] | None:
    """The calibration record, or None (uncalibrated) when absent or not a JSON object."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _majority(labels: list[str]) -> tuple[str, float]:
    counts = Counter(labels)
    top = counts.most_common()
    best_label, best = top[0]
    tied = len(top) > 1 and top[1][1] == best
    label = UNKNOWN if tied or best_label == UNKNOWN else best_label
    return label, best / len(labels)


def _context(trajectory: Trajectory) -> str:
    parts = [
        f"[{step.name}] {step.output if step.output is not None else step.error}"
        for step in trajectory.steps
        if step.kind == "tool"
    ]
    return "\n\n".join(parts) or "(no tool was called)"


def make_rubric_judge(
    judge: Judge,
    repetitions: int = DEFAULT_REPETITIONS,
    *,
    name: str = JUDGE,
    calibration: Mapping[str, Any] | None | str = "load",
) -> Metric:
    """Build the rubric judge Metric.

    Args:
        judge: The Judge to ask (an `LLMClientJudge` on the judge model).
        repetitions: Judgments per answer (default three).
        name: The Metric's name.
        calibration: A calibration record, None for uncalibrated, or "load" (default) to
            read `CALIBRATION_PATH` at each scoring.

    Raises:
        ValueError: When `repetitions` is below one.
    """
    if repetitions < 1:
        raise ValueError("repetitions must be at least 1")

    def rubric(trajectory: Trajectory, case: Case | None) -> Detailed:
        expected = case.expected_outcome if case else None
        messages = RUBRIC_PROMPT.render(
            input=str(case.input) if case else "",
            expected_outcome=str(expected) if expected is not None else "(none given)",
            context=_context(trajectory),
            output=str(trajectory.final_output or ""),
        )
        verdicts = [
            parse_judgment(call_judge(judge, messages, _SCHEMA).text) for _ in range(repetitions)
        ]
        record = load_calibration() if calibration == "load" else calibration
        correctness, c_agree = _majority([v.correctness for v in verdicts])
        grounding, g_agree = _majority([v.grounding for v in verdicts])
        good = sum(v.correctness == "correct" and v.grounding == "grounded" for v in verdicts)
        return Detailed(
            value=good / repetitions,
            comment=next((v.reason for v in verdicts if v.reason), None),
            metadata={
                "correctness": correctness,
                "grounding": grounding,
                "counts": {
                    "correctness": dict(Counter(v.correctness for v in verdicts)),
                    "grounding": dict(Counter(v.grounding for v in verdicts)),
                },
                "agreement": {"correctness": c_agree, "grounding": g_agree},
                "repetitions": [
                    {"correctness": v.correctness, "grounding": v.grounding, "reason": v.reason}
                    for v in verdicts
                ],
                "uncalibrated": not record,
                "prompt": RUBRIC_PROMPT.ref,
                "prompt_hash": RUBRIC_PROMPT.hash,
            },
        )

    return Metric(
        name=name, level="trajectory", fn=rubric, requires=("final_output",), kind="judge"
    )


def register_judge(registry: Any, llm: LLMClient, repetitions: int = DEFAULT_REPETITIONS) -> None:
    """Register the rubric judge, backed by `llm` (the judge model's client), into a Registry."""
    registry.register(make_rubric_judge(LLMClientJudge(llm), repetitions))


def _spread(counts: Mapping[str, int]) -> str:
    return ", ".join(f"{label} {n}" for label, n in sorted(counts.items(), key=lambda kv: -kv[1]))


def format_judge_line(score: Score) -> str:
    """One report line for a judge Score: verdicts, spread and agreement, UNCALIBRATED mark."""
    meta = score.metadata
    mark = " [UNCALIBRATED]" if meta.get("uncalibrated", True) else ""
    agreement = meta["agreement"]
    return (
        f"judge: {meta['correctness']} / {meta['grounding']}{mark} | "
        f"correctness ({_spread(meta['counts']['correctness'])}), "
        f"grounding ({_spread(meta['counts']['grounding'])}) | "
        f"agreement {agreement['correctness']:.2f} / {agreement['grounding']:.2f}"
    )
