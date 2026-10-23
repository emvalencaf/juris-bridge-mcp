"""The citation-existence Score: is every citation in the answer in a tool result?

The agent may only cite what a tool returned. This Metric reads the final answer for CNJ
numbers (`NNNNNNN-DD.AAAA.J.TR.OOOO`, with or without punctuation) and Precedent identifiers
(a kind and a number: `Tema 1002`, `Súmula 331`, `IRDR 12`, `RG 1002`), and looks for each one
in the output of the tool Steps of the same Trajectory (a failed call is not a source).

Both sides are normalised before comparing: a CNJ number to its 20 digits, a Precedent to its
kind sigla and number (`.` thousands separators and `nº` dropped). Results are read for
Precedent ids (`stf-rg-1002`, the server's `<body>-<kind>-<number>`) and for the same wordings
as the answer. The issuing body is not compared: `Súmula 331 do TST` is grounded by any
`SUM` 331 in the results. A wording standing for more than one kind (`Tema` is a `RG` at the
STF and a `RR` at the STJ) is grounded by any of them; `Súmula Vinculante` is only `SV`.

Score semantics: the share of distinct citations found in the results (1.0 when all are). An
answer with no citation, or no answer, is not applicable (None: no Score and no failure), as
`tool_use` does for a Case that expects no tool call. An absent citation is named in the
Score's comment as a fabricated citation. The Metric only reports; nothing is blocked.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from assayer.metrics import Detailed, Metric
from assayer.models import Case, Trajectory

CITATION_EXISTENCE = "citation_existence"

_CNJ = re.compile(r"(?<!\d)(\d{7})-?(\d{2})\.?(\d{4})\.?(\d)\.?(\d{2})\.?(\d{4})(?!\d)")

# Wording of a Precedent in prose -> the kind siglas it may stand for.
_WORDINGS = {
    "súmula vinculante": ("SV",),
    "sumula vinculante": ("SV",),
    "súmula": ("SUM",),
    "sumula": ("SUM",),
    "tema": ("RG", "RR", "IRR"),
    "orientação jurisprudencial": ("OJ",),
}
_SIGLAS = ("SIRDR", "IRDR", "IAC", "IRR", "RR", "RG", "SV", "SUM", "OJ", "ADPF", "ADI", "ADC",
           "ADO", "PUIL")  # fmt: skip
_WORDING = "|".join(sorted((re.escape(w) for w in _WORDINGS), key=len, reverse=True))
_SIGLA = "|".join(_SIGLAS)
_PRECEDENT = re.compile(
    rf"\b(?:(?P<word>(?i:{_WORDING}))|(?P<sigla>{_SIGLA}))"
    r"\s*(?:n[º°o.]{1,2}\s*)?(?P<number>\d{1,3}(?:\.\d{3})+|\d+)(?![\d-])"
)
_ID = re.compile(rf"\b[a-z0-9_]+-(?P<kind>{_SIGLA.lower()})-(?P<number>\d+)\b")


@dataclass(frozen=True)
class Citation:
    """A citation found in a text: how to show it and the keys that ground it."""

    label: str
    keys: frozenset[tuple[str, ...]]


def _number(raw: str) -> str:
    return str(int(raw.replace(".", "")))


def _citations(text: str) -> list[Citation]:
    found: list[Citation] = []
    for match in _CNJ.finditer(text):
        digits = "".join(match.groups())
        punctuated = "{}-{}.{}.{}.{}.{}".format(*match.groups())
        found.append(Citation(f"CNJ {punctuated}", frozenset({("cnj", digits)})))
    rest = _CNJ.sub(" ", text)
    for match in _PRECEDENT.finditer(rest):
        word, sigla = match["word"], match["sigla"]
        kinds = _WORDINGS[word.casefold()] if word else (sigla,)
        number = _number(match["number"])
        keys = frozenset(("precedent", kind, number) for kind in kinds)
        found.append(Citation(" ".join(match[0].split()), keys))
    return found


def extract_citations(text: str) -> list[str]:
    """Return the CNJ numbers and Precedent identifiers cited in a text, as written.

    Args:
        text: The agent's answer.

    Returns:
        One label per citation: `CNJ <punctuated number>` or the Precedent as worded.
    """
    return [citation.label for citation in _citations(text)]


def _available(results: Iterable[str]) -> set[tuple[str, ...]]:
    keys: set[tuple[str, ...]] = set()
    for text in results:
        for citation in _citations(text):
            keys |= citation.keys
        for match in _ID.finditer(text):
            keys.add(("precedent", match["kind"].upper(), _number(match["number"])))
    return keys


def citation_existence(trajectory: Trajectory, case: Case) -> Detailed | None:
    """Score the share of the answer's citations that a tool result of the Trajectory holds.

    Args:
        trajectory: The Trajectory whose final answer and tool results are compared.
        case: The Eval case (unused; the check needs only the Trajectory).

    Returns:
        The share of grounded citations, with a comment naming each fabricated one; None
        (not applicable) when the answer cites nothing or there is no answer.
    """
    citations: list[Citation] = []
    for citation in _citations(trajectory.final_output or ""):
        if all(citation.keys != seen.keys for seen in citations):
            citations.append(citation)
    if not citations:
        return None
    available = _available(
        step.output
        for step in trajectory.steps
        if step.kind == "tool" and not step.error and step.output
    )
    fabricated = [c.label for c in citations if not c.keys & available]
    comment = f"fabricated citation: {'; '.join(fabricated)}" if fabricated else None
    value = (len(citations) - len(fabricated)) / len(citations)
    return Detailed(value, comment=comment, metadata={"fabricated": fabricated})


def register_metrics(registry: Any) -> None:
    """Register the citation-existence metric into a Registry.

    Args:
        registry: The assayer Registry to fill.
    """
    registry.register(Metric(name=CITATION_EXISTENCE, level="trajectory", fn=citation_existence))
