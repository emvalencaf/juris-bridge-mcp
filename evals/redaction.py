"""Redaction of personal data from the text of a Source response.

CPF and CNPJ are found by their fixed patterns and fully masked (`[CPF]`, `[CNPJ]`). Names of
people are found by named-entity recognition (spaCy, Portuguese model `pt_core_news_md`, `PER`
entities only; `ORG`, `LOC` and `MISC` are never touched) and become `[PESSOA N]`. A `Redactor`
numbers the people: the same person, however the name is written, gets the same number for as
long as the `Redactor` lives (one per Cassette). A few role-based patterns (`Autor: ...`,
`Dr. ...`, a name before an OAB registration) back the model up where it misses an obvious name.
CNJ numbers, Court aliases and Precedent kind siglas are never touched, so the citation check
still has something to compare. Best effort, not a guarantee: see `evals/README.md`.
"""

import html
import re
import unicodedata
from collections.abc import Iterator
from functools import cache
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from spacy.language import Language

CPF_PLACEHOLDER = "[CPF]"
CNPJ_PLACEHOLDER = "[CNPJ]"
OAB_PLACEHOLDER = "[OAB]"
PERSON_PLACEHOLDER = "[PESSOA {n}]"
# written by the earlier heuristic redaction; the name is gone, so it cannot be numbered
LEGACY_NAME_PLACEHOLDER = "[NOME]"

NER_MODEL = "pt_core_news_md"

# A CNJ number is matched first only so that its digits are never read as a CPF or CNPJ.
_CNJ = r"\d{7}-?\d{2}\.?\d{4}\.?\d\.?\d{2}\.?\d{4}"
# The hyphen may be wrapped onto the next line or written as the HTML non-breaking hyphen.
_DASH = r"(?:-\s*|&#x2011;|\u2011)?"
_CNPJ = rf"\d{{2}}\.?\d{{3}}\.?\d{{3}}/?\d{{4}}{_DASH}\d{{2}}"
_CPF = rf"\d{{3}}\.?\d{{3}}\.?\d{{3}}{_DASH}\d{{2}}"
_NUMBER = re.compile(
    rf"(?<![\d.\-/])(?:(?P<cnj>{_CNJ})|(?P<cnpj>{_CNPJ})|(?P<cpf>{_CPF}))(?!\d|[.\-/]\d)"
)

# A lawyer's registration: "SP405006", "SP403110-N", "OAB/SP 123456", "OAB 12345".
_OAB_NUMBER = re.compile(
    r"\bOAB\W{0,3}(?:[A-Z]{2}\W{0,3})?\d[\d.]*(?:-?[A-Z]\b|/[A-Z]{2}\b)?"
    r"|\b(?:AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|SC|SP|SE|TO)"
    r"\d{4,6}(?:-?[A-Z]\b)?"
)

_CONNECTORS = frozenset({"de", "da", "do", "dos", "das"})
_CONN = "|".join(sorted(_CONNECTORS))
_WORD = r"[A-ZÀ-Ý][a-zà-ÿ'\u2019]+"
_UPPER = r"[A-ZÀ-Ý][A-ZÀ-Ý'\u2019]+"
_NAME_WORD = rf"(?:{_WORD}|{_UPPER})"

_ROLES = (
    "autor|autora|réu|ré|requerente|requerido|requerida|apelante|apelado|apelada|impetrante|"
    "impetrado|impetrada|agravante|agravado|agravada|exequente|executado|executada|embargante|"
    "embargado|embargada|reclamante|reclamado|reclamada|recorrente|recorrido|recorrida|"
    "paciente|interessado|interessada|advogado|advogada|vítima|testemunha|investigado|"
    "denunciado|denunciada|acusado|acusada"
)
# Fallback patterns; each yields the span of the name only.
_NAME_BEFORE_OAB = re.compile(
    rf"{_UPPER}(?:\s+(?:(?:{_CONN})\s+|(?:DE|DA|DO|DOS|DAS)\s+)?{_UPPER})+"
    rf"(?=\s*\((?:\[OAB\]|(?:CPF:?\s*|ID\s*)?\[CPF\]|(?i:{_ROLES})\)))"
)
_TITLE_NAME = re.compile(
    rf"\b(?:Dr|Dra|Sr|Sra)\.\s+(?P<name>{_NAME_WORD}(?:\s+(?:(?:{_CONN})\s+)?{_NAME_WORD})*)"
)
# A judge or minister by title: only a name of two or more words counts ("Juiz Titular" is not one).
_JUDGE_NAME = re.compile(
    r"(?<![\w])(?i:(?:(?:ministro|ministra|min|desembargador|desembargadora|juiz|juíza|relator|"
    r"relatora|rel)(?:\s+federal)?\.?\s+)+)"
    rf"(?P<name>{_NAME_WORD}(?:\s+(?:(?:{_CONN})\s+)?{_NAME_WORD})+)"
)
_ROLE_NAME = re.compile(
    rf"(?:\b|(?<=[a-zà-ÿ]))(?i:(?:{_ROLES})(?:\(a\))?)\s*[:\-\u2013,]?\s+"
    rf"(?i:(?:(?:dr|dra|sr|sra)\.?\s+)?)"
    rf"(?P<name>(?!(?:Dr|Dra|Sr|Sra)\b){_NAME_WORD}(?:\s+(?:(?:{_CONN})\s+)?{_NAME_WORD})*)"
)

# Institutions, legal vocabulary and courtesy titles: a name is cut at them and they are never
# replaced. Titles (`Dr`, `Ministro`...) stay in the text, only the name after them goes.
_INSTITUTIONAL = frozenset(
    (
        "tribunal justiça superior federal estadual estado ministério público supremo turma "
        "câmara seção recurso especial extraordinário agravo vara comarca súmula vinculante "
        "repercussão geral relator relatora ministro ministra desembargador desembargadora "
        "juiz juíza cível criminal trabalho eleitoral militar regional união república "
        "constituição código lei decreto processo civil penal autos ação apelação embargos "
        "habeas corpus mandado segurança declaração execução fazenda nacional defensoria "
        "advocacia procuradoria conselho órgão pleno plenário julgamento incidente resolução "
        "demandas repetitivas competência assunção tese tema precedente diário eletrônico "
        "publicação intimação sentença decisão despacho acórdão brasil sul norte nordeste "
        "sudeste centro oeste advogado advogada autor autora réu requerente requerido requerida "
        "apelante apelado apelada agravante agravado agravada exequente executado executada "
        "recorrente recorrido recorrida mérito julgado julgada defesa consumidor dr dra sr sra "
        "doutor doutora senhor senhora min rel des inciso artigo art alínea parágrafo caput "
        "titular substituto substituta auxiliar excelentíssimo meritíssimo perícia médica "
        "questão discussão"
    ).split()
)

# Aliases of the Courts and kind siglas of the Precedents: shouted words that are not names.
_PROTECTED = re.compile(
    r"^(?:STF|STJ|TST|TSE|STM|TRF\d*|TRT\d*|TRE-?[A-Z]*|TJ[A-Z]*|"
    r"SUM|SV|OJ|IAC|IRDR|SIRDR|PN|IRR|RR|RG|ADI|ADC|ADO|ADPF|PUIL|CT|NT|NTA|ENU|RC|DPE|OAB|CPF|CNPJ|NOME|PESSOA)$"
)

_PLACEHOLDER = re.compile(r"\[(?:CPF|CNPJ|OAB|NOME|PESSOA \d+)\]")
_TOKEN = re.compile(r"[^\W\d_][\w'\u2019\-]*")
# Two or more shouted words: the model reads them far better in title case.
_SHOUTED_RUN = re.compile(rf"(?<!\w){_UPPER}(?:\s+(?:(?:{_CONN.upper()})\s+)?{_UPPER})+(?!\w)")

# Structured fields that hold a person by their key, whatever the value looks like: the DJEN
# lists the parties (`destinatarios[].nome`) and the lawyers (`advogado.nome`, `numero_oab`)
# of a communication, in capitals, which no pattern over free text would catch.
# `nome` alone is not enough (a DataJud class has one): the object must also carry `polo` (a
# party) or `numero_oab` (a lawyer).
_PERSON_MARKERS = frozenset({"polo", "numero_oab"})

Span = tuple[int, int]


@cache
def _nlp() -> "Language":
    import spacy  # heavy import, only when a name is looked for

    nlp = spacy.load(
        NER_MODEL,
        exclude=["parser", "lemmatizer", "morphologizer", "attribute_ruler", "senter", "tagger"],
    )
    nlp.max_length = 10_000_000
    return nlp


def _is_barrier(word: str) -> bool:
    return word.lower() in _INSTITUTIONAL or bool(_PROTECTED.match(word))


def _runs(text: str, start: int, end: int) -> Iterator[Span]:
    """Yield the stretches of `text[start:end]` made of name words, cut at barrier words."""
    run: list[re.Match[str]] = []
    for m in [*_TOKEN.finditer(text, start, end), None]:
        if m is not None and run and text[run[-1].end() : m.start()].strip():
            # punctuation or markup between two words ends the name ("SILVA</td>")
            yield from _close(run)
            run = []
        if m is not None and not _is_barrier(m.group()):
            run.append(m)
            continue
        yield from _close(run)
        run = []


def _close(run: list[re.Match[str]]) -> Iterator[Span]:
    words = list(run)
    while words and words[0].group().lower() in _CONNECTORS:
        words.pop(0)
    while words and words[-1].group().lower() in _CONNECTORS:
        words.pop()
    if words:
        yield words[0].start(), words[-1].end()


def _ner_spans(text: str) -> list[Span]:
    # placeholders are blanked with digits: the model would take "[CPF]" for a name
    prepared = _PLACEHOLDER.sub(lambda m: "0" * len(m.group()), text)
    prepared = _SHOUTED_RUN.sub(_title_case_run, prepared)
    return [(ent.start_char, ent.end_char) for ent in _nlp()(prepared).ents if ent.label_ == "PER"]


def _title_case_run(match: re.Match[str]) -> str:
    return "".join(
        w if _PROTECTED.match(w) else w.lower() if w.lower() in _CONNECTORS else w.capitalize()
        for w in re.split(r"(\s+)", match.group())
    )


_ROMAN = re.compile(r"^[IVXLCDM]+$")
_GAP = re.compile(rf"^\s+(?:{_CONN})\s+$")


def _words(text: str, span: Span) -> int:
    """Count the words of a span that can belong to a name (no lone letters or numerals)."""
    return sum(1 for t in _TOKEN.findall(text, *span) if len(t) > 1 and not _ROMAN.match(t))


def _fallback_spans(text: str) -> list[Span]:
    spans: list[Span] = []
    for m in _ROLE_NAME.finditer(text):
        # only the stretch right after the role: a barrier ends the name
        first = next(_runs(text, *m.span("name")), None)
        if first is not None and first[0] == m.start("name"):
            spans.append(first)
    for m in _TITLE_NAME.finditer(text):
        first = next(_runs(text, *m.span("name")), None)
        if first is not None and first[0] == m.start("name"):
            spans.append(first)
    for m in _JUDGE_NAME.finditer(text):
        first = next(_runs(text, *m.span("name")), None)
        if first is not None and first[0] == m.start("name") and _words(text, first) > 1:
            spans.append(first)
    for m in _NAME_BEFORE_OAB.finditer(text):
        spans.extend(_runs(text, *m.span()))
    return spans


def _join_across_connectors(text: str, spans: list[Span]) -> list[Span]:
    """Join the pieces the model cuts a name into at a connector ("Paulo" "de" "Tarso Silva")."""
    joined: list[Span] = []
    for start, end in spans:
        if joined and _GAP.match(text[joined[-1][1] : start]):
            joined[-1] = (joined[-1][0], end)
        else:
            joined.append((start, end))
    return joined


def _merge(spans: list[Span]) -> list[Span]:
    merged: list[Span] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def _normalise(name: str) -> tuple[str, ...]:
    """Case, accent, whitespace and connector insensitive tokens of a name."""
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().casefold()
    return tuple(t for t in re.findall(r"[a-z]+", plain) if t not in _CONNECTORS)


def _is_subsequence(small: tuple[str, ...], big: tuple[str, ...]) -> bool:
    it = iter(big)
    return all(token in it for token in small)


class Redactor:
    """Redact personal data and number the people, the same person keeping one number.

    Use one `Redactor` per Cassette: numbers restart from 1 and are shared by every response
    redacted through it, in the order they are met. Two names are the same person when their
    normalised tokens (no case, accents or connectors) are equal, or when both have two or
    more tokens, start and end alike and one is contained in the other in order
    (`João da Silva`, `JOAO SILVA`, `João Carlos Silva`). A single-word name matches only the
    same word; a containment that fits more than one known person counts as a new one.
    """

    def __init__(self) -> None:
        self._people: list[tuple[tuple[str, ...], int]] = []
        self._count = 0

    def person(self, name: str) -> str:
        """Return the placeholder of the person called `name`, numbering it if new."""
        tokens = _normalise(name)
        if name == LEGACY_NAME_PLACEHOLDER or not tokens:
            return name
        for known, number in self._people:
            if known == tokens:
                return PERSON_PLACEHOLDER.format(n=number)
        number = self._same_person(tokens)
        if number is None:
            self._count += 1
            number = self._count
        self._people.append((tokens, number))
        return PERSON_PLACEHOLDER.format(n=number)

    def _same_person(self, tokens: tuple[str, ...]) -> int | None:
        if len(tokens) < 2:
            return None
        found = {
            number
            for known, number in self._people
            if len(known) >= 2
            and known[0] == tokens[0]
            and known[-1] == tokens[-1]
            and (_is_subsequence(known, tokens) or _is_subsequence(tokens, known))
        }
        return found.pop() if len(found) == 1 else None

    def redact(self, value: Any) -> Any:
        """Replace personal data in a Source response with placeholders.

        Args:
            value: Text, or a JSON-like structure (dicts, lists) holding text. Keys are kept.

        Returns:
            The same shape with every string redacted; other values are returned unchanged.
        """
        if isinstance(value, str):
            return self._redact_text(value)
        if isinstance(value, dict):
            return {k: self._redact_field(value, k, v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.redact(v) for v in value]
        return value

    def _redact_field(self, owner: dict[str, Any], key: str, value: Any) -> Any:
        if isinstance(value, str) and _PERSON_MARKERS & owner.keys():
            if key == "nome":
                return self.person(value)
            if key == "numero_oab":
                return OAB_PLACEHOLDER
        return self.redact(value)

    def _redact_text(self, text: str) -> str:
        text = _NUMBER.sub(_mask_number, text)
        text = _OAB_NUMBER.sub(OAB_PLACEHOLDER, text)
        # names are looked for in the text as read (`&eacute;` as "é"), then cut out of the
        # original at the matching offsets
        clean, offsets = _unescape(text)
        spans: list[Span] = []
        for start, end in _join_across_connectors(clean, _ner_spans(clean)):
            # a lone word is mostly a false positive ("Admitido", "Vigente"): see the README
            spans.extend(r for r in _runs(clean, start, end) if _words(clean, r) > 1)
        spans.extend(_fallback_spans(clean))
        out: list[str] = []
        last = 0
        for start, end in _merge(spans):
            out.append(text[last : offsets[start]])
            out.append(self.person(clean[start:end]))
            last = offsets[end]
        out.append(text[last:])
        return "".join(out)


_ENTITY = re.compile(r"&(?:#\d+|#[xX][0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]*);")


def _unescape(text: str) -> tuple[str, list[int]]:
    """Return `text` with HTML entities decoded and, per character, where it starts in `text`."""
    if "&" not in text:
        return text, list(range(len(text) + 1))
    parts: list[str] = []
    offsets: list[int] = []
    last = 0
    for m in [*_ENTITY.finditer(text), None]:
        stop = m.start() if m else len(text)
        parts.append(text[last:stop])
        offsets.extend(range(last, stop))
        if m:
            decoded = html.unescape(m.group())
            parts.append(decoded)
            offsets.extend([m.start()] * len(decoded))
            last = m.end()
    offsets.append(len(text))
    return "".join(parts), offsets


def _mask_number(match: re.Match[str]) -> str:
    if match.group("cnpj"):
        return CNPJ_PLACEHOLDER
    if match.group("cpf"):
        return CPF_PLACEHOLDER
    return match.group()


def redact[T](value: T) -> T:
    """Redact `value` with a fresh `Redactor`: the numbering is local to this call.

    CPF and CNPJ (with or without punctuation) become `[CPF]` and `[CNPJ]`; names of people
    become `[PESSOA N]`. For several responses that must share a numbering, use one `Redactor`.
    """
    return Redactor().redact(value)  # type: ignore[no-any-return]
