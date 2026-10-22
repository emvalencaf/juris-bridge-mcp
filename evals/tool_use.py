"""The tool-use Score: did the agent use the right tool with the right arguments?

assayer's `tool_correctness` and `tool_argument_match` compare multisets of names and pair
calls one to one, so an extra harmless call or another valid route costs points. This metric
is looser, as the spec asks, and is registered the same way as the built-in ones.

An Eval case lists `expected_tool_calls`, each one a requirement the Trajectory must meet:

* a tool name (`"list_coverage"`), or `{"name": "search_precedents", "arguments": {...}}`;
* `name` may be a list of equally good tools (`["search_precedents", "get_precedent"]`);
* `{"any_of": [<call>, <call>]}` accepts either route, each with its own arguments
  (for example `get_publication` by id, or `search_publications` by CNJ number).

A requirement scores the share of its `arguments` keys that the best matching call holds
(strings compared ignoring case and surrounding space); 0 when no call of an accepted tool
exists, 1 when it names no arguments. Keys the case does not mention and calls it does not
expect are never penalised. The Score is the mean over the requirements.
"""

from collections.abc import Mapping
from typing import Any

from assayer.metrics import Detailed, Metric
from assayer.models import Case, Step, Trajectory

TOOL_USE = "tool_use"


def _names(call: Any) -> list[str]:
    name = call.get("name") if isinstance(call, Mapping) else call
    return [name] if isinstance(name, str) else list(name or [])


def _norm(value: Any) -> Any:
    return value.strip().casefold() if isinstance(value, str) else value


def _argument_share(expected: Mapping[str, Any], given: Mapping[str, Any]) -> float:
    if not expected:
        return 1.0
    hits = sum(key in given and _norm(given[key]) == _norm(want) for key, want in expected.items())
    return hits / len(expected)


def _best(call: Any, steps: list[Step]) -> float:
    """Score one expected call (or the best of its alternatives) against the tool Steps."""
    if isinstance(call, Mapping) and "any_of" in call:
        return max((_best(option, steps) for option in call["any_of"]), default=0.0)
    names = _names(call)
    arguments = (call.get("arguments") if isinstance(call, Mapping) else None) or {}
    return max(
        (_argument_share(arguments, step.input or {}) for step in steps if step.name in names),
        default=0.0,
    )


def _describe(call: Any) -> str:
    if isinstance(call, Mapping) and "any_of" in call:
        return " or ".join(_describe(option) for option in call["any_of"])
    names = "/".join(_names(call))
    arguments = call.get("arguments") if isinstance(call, Mapping) else None
    return f"{names}({arguments})" if arguments else names


def tool_use(trajectory: Trajectory, case: Case) -> Detailed | None:
    """Score the tools and arguments of a Trajectory against the Case's expected calls.

    Args:
        trajectory: The Trajectory whose tool Steps are scored.
        case: The Case holding `expected_tool_calls`.

    Returns:
        The mean requirement score, with a comment naming the requirements that fell short;
        None (not applicable) when the Case expects no tool call.
    """
    expected = case.expected_tool_calls
    if not expected:
        return None
    steps = [step for step in trajectory.steps if step.kind == "tool"]
    values = [_best(call, steps) for call in expected]
    short = [_describe(call) for call, value in zip(expected, values, strict=True) if value < 1.0]
    comment = f"not met: {'; '.join(short)}" if short else None
    return Detailed(sum(values) / len(values), comment=comment)


def register_metrics(registry: Any) -> None:
    """Register the tool-use metric into a Registry.

    Args:
        registry: The assayer Registry to fill.
    """
    registry.register(
        Metric(
            name=TOOL_USE,
            level="trajectory",
            requires=("expected_tool_calls",),
            fn=tool_use,
        )
    )
