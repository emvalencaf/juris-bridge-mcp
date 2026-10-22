"""The tool-use Score: tool and arguments against the expected ones, loose on the route."""

from assayer.models import Case, Step, Trajectory
from assayer.registries import Registry

from evals.tool_use import TOOL_USE, register_metrics, tool_use


def trajectory(*calls: tuple[str, dict]) -> Trajectory:
    return Trajectory(steps=[Step(kind="tool", name=n, input=a) for n, a in calls])


def score(expected, *calls) -> float:
    case = Case(input="q", expected_tool_calls=expected)
    result = tool_use(trajectory(*calls), case)
    return result.value


def test_the_expected_tool_with_the_expected_arguments_scores_one():
    expected = [{"name": "get_precedent", "arguments": {"id": "stf-rg-1002"}}]

    assert score(expected, ("get_precedent", {"id": "stf-rg-1002"})) == 1.0


def test_a_missing_tool_scores_zero():
    expected = [{"name": "get_precedent", "arguments": {"id": "x"}}]

    assert score(expected, ("search_precedents", {"query": "x"})) == 0.0


def test_the_right_tool_with_wrong_arguments_scores_the_share_of_right_keys():
    expected = [{"name": "search_precedents", "arguments": {"number": "1002", "kind": "RG"}}]

    assert score(expected, ("search_precedents", {"number": "1002", "kind": "SUM"})) == 0.5


def test_only_the_keys_the_case_specifies_are_compared():
    expected = [{"name": "search_precedents", "arguments": {"number": "1002"}}]

    got = ("search_precedents", {"number": "1002", "court": "stf", "limit": 5})
    assert score(expected, got) == 1.0


def test_extra_harmless_calls_are_not_marked_wrong():
    expected = [{"name": "search_precedents", "arguments": {"number": "1002"}}]

    assert (
        score(
            expected,
            ("list_coverage", {}),
            ("search_precedents", {"number": "1002"}),
            ("get_precedent", {"id": "stf-rg-1002"}),
        )
        == 1.0
    )


def test_a_name_may_list_alternatives():
    expected = [{"name": ["search_precedents", "get_precedent"], "arguments": {}}]

    assert score(expected, ("get_precedent", {"id": "a"})) == 1.0


def test_any_of_accepts_an_alternative_route_with_its_own_arguments():
    expected = [
        {
            "any_of": [
                {"name": "get_publication", "arguments": {"id": "p1"}},
                {"name": "search_publications", "arguments": {"cnj_number": "1-2"}},
            ]
        }
    ]

    assert score(expected, ("search_publications", {"cnj_number": "1-2", "court": "tjsp"})) == 1.0
    assert score(expected, ("get_publication", {"id": "p1"})) == 1.0
    assert score(expected, ("list_coverage", {})) == 0.0


def test_the_best_matching_call_of_the_right_tool_counts():
    expected = [{"name": "search_precedents", "arguments": {"number": "1002"}}]

    got = [("search_precedents", {"query": "x"}), ("search_precedents", {"number": "1002"})]
    assert score(expected, *got) == 1.0


def test_strings_compare_ignoring_case_and_surrounding_space():
    expected = [{"name": "search_publications", "arguments": {"court": "TJSP"}}]

    assert score(expected, ("search_publications", {"court": " tjsp "})) == 1.0


def test_a_bare_name_expects_the_tool_only():
    assert score(["list_coverage"], ("list_coverage", {})) == 1.0


def test_the_score_is_the_mean_over_the_expected_calls():
    expected = [{"name": "list_coverage"}, {"name": "get_precedent", "arguments": {"id": "a"}}]

    assert score(expected, ("list_coverage", {})) == 0.5


def test_no_expected_calls_is_not_applicable():
    case = Case(input="q", expected_tool_calls=[])

    assert tool_use(trajectory(("list_coverage", {})), case) is None


def test_the_comment_names_what_was_missed():
    case = Case(input="q", expected_tool_calls=[{"name": "get_precedent"}])

    result = tool_use(trajectory(), case)

    assert result.value == 0.0 and "get_precedent" in result.comment


def test_it_registers_as_a_metric_named_tool_use():
    registry = Registry()

    register_metrics(registry)

    assert registry.get(TOOL_USE).requires == ("expected_tool_calls",)
