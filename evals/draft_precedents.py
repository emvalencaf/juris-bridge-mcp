"""Draft Eval cases about Precedents, negatives and Coverage, recorded from the live Sources.

Run by hand, opt-in, read-only and paced (see `evals.record`):

    JURIS_BRIDGE_EVALS_RECORD=1 uv run --group evals python -m evals.draft_precedents

Each `DraftSpec` names the question, the tool calls recorded for it and the alternatives a good
agent may start with. The calls run on the real server over the recording transport, which
saves a redacted, dated Cassette named after the case id. Every expected value (the Precedent
ids to retrieve, the status and thesis facts, the not_covered reason) is copied from the
recorded responses and never written from memory. A case whose recording does not show what
the spec claims (a negative that found something, a lookup that found nothing) is dropped and
its Cassette removed, so a draft always matches its Cassette. Drafts go to
`evals/cases/drafts/precedents.json`, unvalidated, and count toward no result.

Give case ids as arguments to re-record only those; the others stay in the drafts file.
Recording stops at the first `source_unavailable`: an unreachable or blocking Source is not
retried.
"""

import asyncio
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastmcp import Client

from evals.cassette import CASSETTES_DIR, cassette_path
from evals.record import RecordingDisabledError, RecordOptions, record_case

DRAFTS_FILE = Path(__file__).parent / "cases" / "drafts" / "precedents.json"
MIN_INTERVAL_SECONDS = 2.0
SEARCH_REFERENCES = 3
THESIS_CHARS = 200

Call = tuple[str, dict[str, Any]]


class SourceUnavailableError(RuntimeError):
    """A Source did not answer; recording stops without retrying."""


@dataclass
class Recorded:
    """What the recorded calls returned: parsed data, or the error text, per call."""

    results: list[tuple[str, dict[str, Any], dict[str, Any] | None, str | None]] = field(
        default_factory=list
    )

    def data(self, tool: str, index: int = 0) -> dict[str, Any]:
        """Return the data of the `index`-th successful call to `tool`."""
        found = [d for t, _a, d, _e in self.results if t == tool and d is not None]
        return found[index]

    def errors(self) -> list[str]:
        """Return the error texts of the failed calls."""
        return [e for _t, _a, _d, e in self.results if e is not None]


@dataclass(frozen=True)
class DraftSpec:
    """One draft: the question, what to record and the shape of a good start."""

    id: str
    input: str
    kind: str  # "lookup" or "search" (the consistency rule of the Eval case)
    calls: list[Call]
    expected: list[dict[str, Any]]  # `expected_tool_calls` entries
    outcome: Callable[[Recorded], str]
    references: Callable[[Recorded], list[str]] = lambda _r: []
    check: Callable[[Recorded], str | None] = lambda _r: None


def _items(recorded: Recorded) -> list[dict[str, Any]]:
    return recorded.data("search_precedents")["items"]


def _clean(text: str | None) -> str | None:
    """Return a thesis usable as an expected fact, or None (empty, unknown or redacted)."""
    if not text or "[NOME]" in text or text.strip().lower() == "não informado":
        return None
    text = " ".join(text.split())
    return text if len(text) <= THESIS_CHARS else text[:THESIS_CHARS].rstrip() + "..."


def _found(recorded: Recorded) -> str | None:
    if recorded.errors():
        return f"a call failed: {recorded.errors()[0][:120]}"
    return None if _items(recorded) else "the search returned nothing"


def _empty(recorded: Recorded) -> str | None:
    if recorded.errors():
        return f"a call failed: {recorded.errors()[0][:120]}"
    total = recorded.data("search_precedents")["total"]
    return None if total == 0 else f"expected an empty result, the Source has {total}"


def _lookup_outcome(recorded: Recorded) -> str:
    item = _items(recorded)[0]
    text = (
        f"Identifies the Precedent {item['id']} ({item['kind']} {item['number']}, "
        f"{item['court']}) with the status the tool returned ({item['status']!r})"
    )
    thesis = _clean(item.get("thesis"))
    if thesis:
        text += f" and states its thesis as the tool returned it: {thesis!r}"
    else:
        text += ", and does not invent a thesis the tool did not give"
    return text + ". Cites no Precedent the tools did not return."


def _search_outcome(recorded: Recorded) -> str:
    data = recorded.data("search_precedents")
    ids = [i["id"] for i in data["items"][:SEARCH_REFERENCES]]
    return (
        f"Presents Precedents the search returned (the Source counted {data['total']}; for "
        f"example {', '.join(ids)}), with their thesis as returned, and cites no Precedent the "
        "tools did not return."
    )


def _ids(recorded: Recorded) -> list[str]:
    return [i["id"] for i in _items(recorded)[:SEARCH_REFERENCES]]


def _first_id(recorded: Recorded) -> list[str]:
    return [_items(recorded)[0]["id"]]


def _empty_outcome(what: str) -> Callable[[Recorded], str]:
    def outcome(recorded: Recorded) -> str:
        total = recorded.data("search_precedents")["total"]
        return (
            f"States that the BNP returned no Precedent for {what} (total {total}), says an "
            "empty result does not prove none exists, and invents no Precedent, number or thesis."
        )

    return outcome


def _search(**arguments: Any) -> Call:
    return ("search_precedents", arguments)


def _by_number(court: str, kind: str, number: str, query: str) -> list[dict[str, Any]]:
    return [
        {
            "any_of": [
                {
                    "name": "search_precedents",
                    "arguments": {"court": court, "kind": kind, "number": number},
                },
                {"name": "search_precedents", "arguments": {"number": number, "kind": kind}},
                {"name": "search_precedents", "arguments": {"query": query}},
            ]
        }
    ]


def _lookup(case_id: str, input_: str, court: str, kind: str, number: str, query: str) -> DraftSpec:
    return DraftSpec(
        id=case_id,
        input=input_,
        kind="lookup",
        calls=[_search(court=court, kind=kind, number=number)],
        expected=_by_number(court, kind, number, query),
        outcome=_lookup_outcome,
        references=_first_id,
        check=_found,
    )


def _topic(case_id: str, input_: str, **arguments: Any) -> DraftSpec:
    return DraftSpec(
        id=case_id,
        input=input_,
        kind="search",
        calls=[_search(**arguments)],
        expected=[
            {
                "name": "search_precedents",
                "arguments": dict(arguments),
            }
        ],
        outcome=_search_outcome,
        references=_ids,
        check=_found,
    )


def _negative(
    case_id: str, input_: str, what: str, expected: list[dict[str, Any]], **arguments: Any
) -> DraftSpec:
    return DraftSpec(
        id=case_id,
        input=input_,
        kind="lookup",
        calls=[_search(**arguments)],
        expected=expected,
        outcome=_empty_outcome(what),
        check=_empty,
    )


def _not_covered_outcome(recorded: Recorded) -> str:
    message = json.loads(recorded.errors()[0])["message"]
    return (
        f"Tells the user the server cannot answer this, as the tools declared: {message!r} "
        "It lists no Publication and suggests no Court it did not see in list_coverage."
    )


def _is_not_covered(recorded: Recorded) -> str | None:
    errors = recorded.errors()
    if len(errors) != 1 or '"not_covered"' not in errors[0]:
        return f"expected one not_covered error, got {errors!r}"
    return None


def _not_covered(case_id: str, input_: str, **arguments: Any) -> DraftSpec:
    return DraftSpec(
        id=case_id,
        input=input_,
        kind="lookup",
        calls=[("list_coverage", {}), ("search_publications", arguments)],
        expected=[
            {
                "any_of": [
                    "list_coverage",
                    {"name": "search_publications", "arguments": {"court": arguments["court"]}},
                ]
            }
        ],
        outcome=_not_covered_outcome,
        check=_is_not_covered,
    )


def _coverage_outcome(recorded: Recorded) -> str:
    sources = recorded.data("list_coverage")["sources"]
    names = ", ".join(f"{s['source']} ({s['kind']})" for s in sources)
    return (
        f"Describes only what list_coverage returned: the Sources {names}; names no Source or "
        "Court the tool did not list and does not promise unlisted data."
    )


def _coverage_case(case_id: str, input_: str) -> DraftSpec:
    return DraftSpec(
        id=case_id,
        input=input_,
        kind="lookup",
        calls=[("list_coverage", {})],
        expected=["list_coverage"],
        outcome=_coverage_outcome,
        check=lambda r: None if r.data("list_coverage")["sources"] else "no sources",
    )


SPECS: list[DraftSpec] = [
    _lookup(
        "draft-prec-sv-11",
        "O que diz a Súmula Vinculante 11 do STF?",
        "stf",
        "SV",
        "11",
        "súmula vinculante 11",
    ),
    _lookup(
        "draft-prec-sum-stj-7",
        "Qual é o enunciado da Súmula 7 do STJ?",
        "stj",
        "SUM",
        "7",
        "súmula 7",
    ),
    _lookup(
        "draft-prec-rg-69",
        "Qual é a tese do Tema 69 da repercussão geral do STF?",
        "stf",
        "RG",
        "69",
        "tema 69",
    ),
    _lookup(
        "draft-prec-sum-stj-297",
        "A Súmula 297 do STJ ainda está em vigor? O que ela diz?",
        "stj",
        "SUM",
        "297",
        "súmula 297",
    ),
    _lookup(
        "draft-prec-sum-stj-479",
        "Qual é a Súmula 479 do STJ e qual o seu status?",
        "stj",
        "SUM",
        "479",
        "súmula 479",
    ),
    DraftSpec(
        id="draft-prec-sv-25-get",
        input="Mostre em detalhes a Súmula Vinculante 25 do STF, com histórico de status.",
        kind="lookup",
        calls=[
            _search(court="stf", kind="SV", number="25"),
            ("get_precedent", {"id": "stf-sv-25"}),
        ],
        expected=[
            *_by_number("stf", "SV", "25", "súmula vinculante 25"),
            {"name": "get_precedent", "arguments": {"id": "stf-sv-25"}},
        ],
        outcome=_lookup_outcome,
        references=_first_id,
        check=_found,
    ),
    _topic(
        "draft-prec-tst-outsourcing",
        "Há precedentes do TST sobre terceirização de atividade-fim?",
        query="terceirização atividade-fim",
        court="tst",
    ),
    _topic(
        "draft-prec-stj-prescricao-intercorrente",
        "Quais recursos repetitivos do STJ tratam de prescrição intercorrente?",
        query="prescrição intercorrente",
        court="stj",
        kind="RR",
    ),
    _topic(
        "draft-prec-stj-negativacao",
        "O STJ tem precedente sobre dano moral por inscrição indevida em cadastro de "
        "inadimplentes?",
        query="dano moral inscrição indevida cadastro de inadimplentes",
        court="stj",
    ),
    _topic(
        "draft-prec-stf-honorarios",
        "Quais temas de repercussão geral do STF tratam de honorários sucumbenciais da "
        "Fazenda Pública?",
        query="honorários sucumbenciais Fazenda Pública",
        court="stf",
        kind="RG",
    ),
    _topic(
        "draft-prec-tjsp-irdr",
        "Quais IRDRs do TJSP existem? Liste alguns.",
        court="tjsp",
        kind="IRDR",
        limit=3,
    ),
    _negative(
        "draft-prec-neg-stj-sum-9999",
        "O que diz a Súmula 9999 do STJ?",
        "STJ súmula 9999",
        _by_number("stj", "SUM", "9999", "súmula 9999"),
        court="stj",
        kind="SUM",
        number="9999",
    ),
    _negative(
        "draft-prec-neg-rg-99999",
        "Qual é a tese do Tema 99999 de repercussão geral do STF?",
        "STF repercussão geral tema 99999",
        _by_number("stf", "RG", "99999", "tema 99999"),
        court="stf",
        kind="RG",
        number="99999",
    ),
    _negative(
        "draft-prec-neg-sv-cripto",
        "Existe súmula vinculante do STF sobre criptomoedas?",
        "súmula vinculante sobre criptomoeda",
        [
            {
                "name": "search_precedents",
                "arguments": {"query": "criptomoeda blockchain", "court": "stf", "kind": "SV"},
            }
        ],
        query="criptomoeda blockchain",
        court="stf",
        kind="SV",
    ),
    _negative(
        "draft-prec-neg-nonsense-stj",
        "O STJ tem algum precedente sobre 'xyzzyqwertz'?",
        "'xyzzyqwertz' no STJ",
        [{"name": "search_precedents", "arguments": {"query": "xyzzyqwertz", "court": "stj"}}],
        query="xyzzyqwertz",
        court="stj",
    ),
    _negative(
        "draft-prec-neg-tst-sum-331",
        "O que diz a Súmula 331 do TST?",
        "TST súmula 331",
        _by_number("tst", "SUM", "331", "súmula 331"),
        court="tst",
        kind="SUM",
        number="331",
    ),
    _coverage_case(
        "draft-cov-what-covered",
        "Quais fontes e tribunais este servidor consegue consultar? Ele cobre legislação federal?",
    ),
    _not_covered(
        "draft-cov-stf-publications",
        "Quais publicações do STF saíram no diário em 15/10/2026?",
        query="intimação",
        court="stf",
        date_from="2026-10-15",
        date_to="2026-10-15",
    ),
    _not_covered(
        "draft-cov-tre-publications",
        "Mostre as publicações do TRE de São Paulo de 15/10/2026.",
        query="intimação",
        court="tre-sp",
        date_from="2026-10-15",
        date_to="2026-10-15",
    ),
    _not_covered(
        "draft-cov-tjsp-before-start",
        "Quais publicações do TJSP saíram em 10/12/2024?",
        query="intimação",
        court="tjsp",
        date_from="2024-12-10",
        date_to="2024-12-10",
    ),
]


async def _record(spec: DraftSpec, root: Path) -> Recorded | None:
    """Record one spec; return what it returned, or None when it does not match the spec."""
    recorded = Recorded()

    async def run(client: Client[Any]) -> None:
        for name, arguments in spec.calls:
            result = await client.call_tool(name, arguments, raise_on_error=False)
            if result.is_error:
                text = "".join(getattr(block, "text", "") for block in result.content)
                if '"source_unavailable"' in text:
                    raise SourceUnavailableError(f"{spec.id}: {text[:200]}")
                recorded.results.append((name, arguments, None, text))
            else:
                recorded.results.append((name, arguments, result.structured_content, None))

    await record_case(
        spec.id, run, root=root, options=RecordOptions(min_interval=MIN_INTERVAL_SECONDS)
    )
    problem = spec.check(recorded)
    if problem is not None:
        cassette_path(spec.id, root=root).unlink()
        print(f"dropped {spec.id}: {problem}", file=sys.stderr)
        return None
    return recorded


def eval_case(spec: DraftSpec, recorded: Recorded) -> dict[str, Any]:
    """Build the Eval case of a spec from what its calls returned."""
    return {
        "id": spec.id,
        "input": spec.input,
        "expected_tool_calls": spec.expected,
        "reference_context_ids": spec.references(recorded),
        "expected_outcome": spec.outcome(recorded),
        "expected_state": {"kind": spec.kind},
    }


async def record_drafts(
    specs: list[DraftSpec] | None = None,
    *,
    root: Path = CASSETTES_DIR,
    out: Path = DRAFTS_FILE,
) -> list[dict[str, Any]]:
    """Record every spec and write the draft Eval cases that matched their recording."""
    kept = json.loads(out.read_text(encoding="utf-8")) if out.exists() else []
    cases: list[dict[str, Any]] = []
    try:
        for spec in SPECS if specs is None else specs:
            recorded = await _record(spec, root)
            if recorded is not None:
                cases.append(eval_case(spec, recorded))
                print(f"recorded {spec.id}")
    finally:
        done = {case["id"] for case in cases}
        cases = [case for case in kept if case["id"] not in done] + cases
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return cases


def main() -> int:
    """Record the drafts from the live Sources; the exit code is 1 when it must stop."""
    try:
        only = sys.argv[1:]
        cases = asyncio.run(record_drafts([s for s in SPECS if not only or s.id in only]))
    except RecordingDisabledError as refused:
        print(refused, file=sys.stderr)
        return 1
    except SourceUnavailableError as stop:
        print(f"Source unavailable, stopped without retrying: {stop}", file=sys.stderr)
        return 1
    print(f"{len(cases)} draft(s) written to {DRAFTS_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
