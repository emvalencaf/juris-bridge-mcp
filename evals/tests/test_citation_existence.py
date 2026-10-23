"""The citation-existence Score: every CNJ number or Precedent cited must be in a tool result."""

from assayer.models import Case, Dataset, Step, Trajectory
from assayer.registries import Registry

from evals.citation_existence import (
    CITATION_EXISTENCE,
    citation_existence,
    extract_citations,
    register_metrics,
)
from evals.dataset import load_split
from evals.llm import ChatResult, ScriptedLLMClient, ToolCall, Usage
from evals.run import format_experiment, run_eval

CNJ = "1234567-76.2025.8.26.0100"
PRECEDENT = '{"id": "stf-rg-1002", "number": 1002, "kind": "RG"}'


def run(answer: str | None, *results: str):
    steps = [Step(kind="tool", name="t", output=text) for text in results]
    return citation_existence(Trajectory(steps=steps, final_output=answer), Case(input="q"))


def test_a_cnj_number_found_in_the_tool_results_is_grounded():
    result = run(f"O processo {CNJ} tem uma publicação.", f'{{"cnj_number": "{CNJ}"}}')

    assert result.value == 1.0 and result.comment is None


def test_a_cnj_number_absent_from_the_tool_results_is_flagged_by_name():
    result = run(f"Veja {CNJ} e 7654321-10.2024.8.26.0001.", f'{{"cnj_number": "{CNJ}"}}')

    assert result.value == 0.5
    assert "fabricated citation" in result.comment
    assert "7654321-10.2024.8.26.0001" in result.comment and CNJ not in result.comment


def test_an_unpunctuated_cnj_number_in_the_answer_matches_a_punctuated_one_in_the_results():
    assert run("Processo 12345677620258260100.", f"cnj {CNJ}").value == 1.0


def test_a_punctuated_cnj_number_in_the_answer_matches_an_unpunctuated_one_in_the_results():
    assert run(f"Processo {CNJ}.", '{"raw_number": "12345677620258260100"}').value == 1.0


def test_a_precedent_cited_by_theme_matches_the_id_in_the_results():
    assert run("A tese do Tema 1002 do STF diz...", PRECEDENT).value == 1.0


def test_a_precedent_absent_from_the_results_is_flagged():
    result = run("Aplica-se a Súmula 331 e o Tema 1002.", PRECEDENT)

    assert result.value == 0.5
    assert "Súmula 331" in result.comment and "Tema 1002" not in result.comment


def test_precedent_kinds_and_numbers_are_normalised_on_both_sides():
    results = '{"id": "tst-sum-331"} {"id": "stj-irdr-12"}'
    answer = "Súmula nº 331, IRDR n. 12 e Tema 1.002 (RG 1002)."

    result = run(answer, results, PRECEDENT)

    assert result.value == 1.0


def test_a_sumula_vinculante_is_not_grounded_by_an_ordinary_sumula_of_the_same_number():
    assert run("Súmula Vinculante 10.", '{"id": "tst-sum-10"}').value == 0.0


def test_a_tema_matches_a_repetitive_theme_too():
    assert run("Tema 1002 do STJ.", '{"id": "stj-rr-1002"}').value == 1.0


def test_an_answer_without_citation_is_not_applicable():
    assert run("Não encontrei nada.", PRECEDENT) is None


def test_a_missing_answer_is_not_applicable():
    assert run(None, PRECEDENT) is None


def test_a_citation_with_no_tool_result_at_all_is_flagged():
    assert run(f"Veja {CNJ}.").value == 0.0


def test_a_failed_tool_call_is_not_a_source():
    steps = [Step(kind="tool", name="t", output=CNJ, error="boom")]

    result = citation_existence(
        Trajectory(steps=steps, final_output=f"Veja {CNJ}."), Case(input="q")
    )

    assert result.value == 0.0


def test_a_cnj_number_is_not_read_as_a_precedent_number():
    assert extract_citations("Processo 1234567-76.2025.8.26.0100 apenas.") == [
        "CNJ 1234567-76.2025.8.26.0100"
    ]


def test_the_metric_is_registered_and_needs_no_case_field():
    registry = Registry()
    register_metrics(registry)

    metric = registry.get(CITATION_EXISTENCE)

    assert metric.level == "trajectory" and not metric.requires


def test_a_run_scores_and_reports_a_fabricated_citation_without_failing():
    case = next(c for c in load_split("seed").cases if c.id == "seed-publications-by-cnj")
    search = {
        "cnj_number": CNJ,
        "court": "tjsp",
        "date_from": "2026-10-15",
        "date_to": "2026-10-15",
    }
    llm = ScriptedLLMClient(
        [
            ChatResult(tool_calls=(ToolCall("search_publications", search),), usage=Usage(1, 1)),
            ChatResult(text=f"Veja {CNJ} e 7654321-10.2024.8.26.0001.", usage=Usage(1, 1)),
        ]
    )

    experiment = run_eval(Dataset("seed", [case]), llm)

    (found,) = [s for s in experiment.scores if s.name == CITATION_EXISTENCE]
    assert found.value == 0.5 and not experiment.failures
    text = format_experiment(experiment)
    assert "citation_existence 0.50" in text and "fabricated citation: CNJ 7654321-10" in text
    assert "mean citation_existence: 0.50" in text
