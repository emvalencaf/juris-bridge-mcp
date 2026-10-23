"""Redaction of personal data from the text of a Source response.

CPF and CNPJ are found by their fixed patterns. Names of people are found by heuristics only
(see `evals/README.md` for what they miss). CNJ numbers, Court aliases and Precedent kind
siglas are never touched, so the citation check still has something to compare.
"""

import re
from typing import Any

CPF_PLACEHOLDER = "[CPF]"
CNPJ_PLACEHOLDER = "[CNPJ]"
NAME_PLACEHOLDER = "[NOME]"

# A CNJ number is matched first only so that its digits are never read as a CPF or CNPJ.
_CNJ = r"\d{7}-?\d{2}\.?\d{4}\.?\d\.?\d{2}\.?\d{4}"
_CNPJ = r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}"
_CPF = r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}"
_NUMBER = re.compile(
    rf"(?<![\d.\-/])(?:(?P<cnj>{_CNJ})|(?P<cnpj>{_CNPJ})|(?P<cpf>{_CPF}))(?!\d|[.\-/]\d)"
)

_CONNECTORS = frozenset({"de", "da", "do", "dos", "das"})
_CONN = "|".join(sorted(_CONNECTORS))
_WORD = r"[A-ZÀ-Ý][a-zà-ÿ'\u2019]+"
_UPPER = r"[A-ZÀ-Ý][A-ZÀ-Ý'\u2019]+"
_NAME_WORD = rf"(?:{_WORD}|{_UPPER})"

# Two or more capitalised words, optionally joined by connectors ("Ana Paula da Silva").
_TITLE_RUN = re.compile(rf"\b{_WORD}(?:\s+(?:(?:{_CONN})\s+)?{_WORD})+")

_ROLES = (
    "autor|autora|réu|ré|requerente|requerido|requerida|apelante|apelado|apelada|impetrante|"
    "impetrado|impetrada|agravante|agravado|agravada|exequente|executado|executada|embargante|"
    "embargado|embargada|reclamante|reclamado|reclamada|recorrente|recorrido|recorrida|"
    "paciente|interessado|interessada|advogado|advogada|vítima|testemunha|investigado|"
    "denunciado|denunciada|acusado|acusada"
)
OAB_PLACEHOLDER = "[OAB]"
# A lawyer's registration: "SP405006", "SP403110-N", "OAB/SP 123456", "OAB 12345".
_OAB_NUMBER = re.compile(
    r"\bOAB\W{0,3}(?:[A-Z]{2}\W{0,3})?\d[\d.]*(?:-?[A-Z]\b|/[A-Z]{2}\b)?|\b(?:AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|SC|SP|SE|TO)\d{4,6}(?:-?[A-Z]\b)?"
)
# "JOSÉ EDUARDO GOMES DA COSTA ([OAB])": the name a registration in parentheses belongs to.
_NAME_BEFORE_OAB = re.compile(
    rf"{_UPPER}(?:\s+(?:(?:{_CONN})\s+|(?:DE|DA|DO|DOS|DAS)\s+)?{_UPPER})+(?=\s*\((?:\[OAB\]|(?:CPF:?\s*|ID\s*)?\[CPF\]|(?i:{_ROLES})\)))"
)
# A name after a courtesy title ("Dr. FELIPE GONÇALVES PINTO"); handled like a role's name.
_TITLE_NAME = re.compile(
    rf"\b(?P<role>(?:Dr|Dra|Sr|Sra)\.)(?P<sep>\s+)"
    rf"(?P<name>{_NAME_WORD}(?:\s+(?:(?:{_CONN})\s+)?{_NAME_WORD})*)"
)
_ROLE_NAME = re.compile(
    rf"(?:\b|(?<=[a-zà-ÿ]))(?P<role>(?i:(?:{_ROLES})(?:\(a\))?))(?P<sep>\s*[:\-\u2013,]?\s+(?i:(?:(?:dr|dra|sr|sra)\.?\s+)?))"
    rf"(?P<name>(?!(?:Dr|Dra|Sr|Sra)\b){_NAME_WORD}(?:\s+(?:(?:{_CONN})\s+)?{_NAME_WORD})*)",
)

# Institutions and legal vocabulary: a run is split at them and they are never replaced.
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
        "recorrente recorrido recorrida"
    ).split()
)

# Aliases of the Courts and kind siglas of the Precedents: shouted words that are not names.
_PROTECTED = re.compile(
    r"^(?:STF|STJ|TST|TSE|STM|TRF\d*|TRT\d*|TRE-?[A-Z]*|TJ[A-Z]*|"
    r"SUM|SV|OJ|IAC|IRDR|SIRDR|PN|IRR|RR|RG|ADI|ADC|ADO|ADPF|PUIL|CT|NT|NTA|ENU|RC)$"
)


def _is_institutional(word: str) -> bool:
    return word.lower() in _INSTITUTIONAL


def _split_at_institutional(words: list[str]) -> list[list[str]]:
    """Group consecutive non-institutional words; institutional ones stand alone."""
    groups: list[list[str]] = []
    for word in words:
        if _is_institutional(word):
            groups.append([word])
        elif groups and not _is_institutional(groups[-1][0]):
            groups[-1].append(word)
        else:
            groups.append([word])
    return groups


def _redact_title_run(match: re.Match[str]) -> str:
    """Replace each sub-run of two or more name words; institutional words split the run."""
    out: list[str] = []
    for group in _split_at_institutional(match.group().split()):
        names = [w for w in group if w not in _CONNECTORS]
        if len(names) >= 2 and not _is_institutional(group[0]):
            # a connector at either end belongs to the sentence, not to the name
            lead = [w for w in group[:1] if w in _CONNECTORS]
            tail: list[str] = []
            while group and group[-1] in _CONNECTORS:
                tail.insert(0, group.pop())
            out.extend([*lead, NAME_PLACEHOLDER, *tail])
        else:
            out.extend(group)
    return " ".join(out)


def _redact_role_name(match: re.Match[str]) -> str:
    kept: list[str] = []
    for word in match.group("name").split():
        if _PROTECTED.match(word) or _is_institutional(word):
            break
        kept.append(word)
    while kept and kept[-1] in _CONNECTORS:
        kept.pop()
    if not kept:
        return match.group()
    name = match.group("name")
    consumed = len(" ".join(kept))
    return f"{match.group('role')}{match.group('sep')}{NAME_PLACEHOLDER}{name[consumed:]}"


def _redact_number(match: re.Match[str]) -> str:
    if match.group("cnpj"):
        return CNPJ_PLACEHOLDER
    if match.group("cpf"):
        return CPF_PLACEHOLDER
    return match.group()


def _redact_text(text: str) -> str:
    text = _NUMBER.sub(_redact_number, text)
    for _ in range(2):  # a role inside the tail of a previous match needs a second pass
        text = _ROLE_NAME.sub(_redact_role_name, text)
    text = _TITLE_NAME.sub(_redact_role_name, text)
    text = _OAB_NUMBER.sub(OAB_PLACEHOLDER, text)
    text = _NAME_BEFORE_OAB.sub(NAME_PLACEHOLDER, text)
    return _TITLE_RUN.sub(_redact_title_run, text)


# Structured fields that hold a person by their key, whatever the value looks like: the DJEN
# lists the parties (`destinatarios[].nome`) and the lawyers (`advogado.nome`, `numero_oab`)
# of a communication, in capitals, which no pattern over free text would catch.
# `nome` alone is not enough (a DataJud class has one): the object must also carry `polo` (a
# party) or `numero_oab` (a lawyer).
_PERSON_MARKERS = frozenset({"polo", "numero_oab"})


def _redact_field(owner: dict[str, Any], key: str, value: Any) -> Any:
    if isinstance(value, str) and _PERSON_MARKERS & owner.keys():
        if key == "nome":
            return NAME_PLACEHOLDER
        if key == "numero_oab":
            return OAB_PLACEHOLDER
    return redact(value)


def redact[T](value: T) -> T:
    """Replace personal data in a Source response with placeholders.

    CPF and CNPJ (with or without punctuation) become `[CPF]` and `[CNPJ]`. Names of people
    become `[NOME]` on a best-effort basis: names after a party role and runs of capitalised
    words. CNJ numbers, Court aliases and Precedent kind siglas are left as they are.

    Args:
        value: Text, or a JSON-like structure (dicts, lists) holding text. Keys are kept.

    Returns:
        The same shape with every string redacted; other values are returned unchanged.
    """
    result: Any = value
    if isinstance(value, str):
        result = _redact_text(value)
    elif isinstance(value, dict):
        result = {k: _redact_field(value, k, v) for k, v in value.items()}
    elif isinstance(value, list):
        result = [redact(v) for v in value]
    return result  # type: ignore[no-any-return]
