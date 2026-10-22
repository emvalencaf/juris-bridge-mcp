"""What kind of act a Publication is, classified from its labels and its text.

The DJEN labels do not say it: TJSP files sentenças, decisões, despachos and notices under a
plain "Intimação", and STJ files every monocratic act as "DESPACHO / DECISÃO". Only the text
separates them, so this is a heuristic; when it finds no marker it answers `AMBIGUOUS`
instead of guessing. Its known weak spot is the line between a despacho and an interlocutory
decision.
"""

import re
import unicodedata
from enum import StrEnum


class PublicationKind(StrEnum):
    """The kind a Publication is presented with."""

    ACORDAO = "acordao"
    SENTENCA = "sentenca"
    DECISAO_MONOCRATICA = "decisao_monocratica"
    DECISAO_INTERLOCUTORIA = "decisao_interlocutoria"
    AMBIGUOUS = "ambiguous"
    # Despachos, intimações, editais and notices: classified so they can be dropped, never shown.
    NOT_A_DECISION = "not_a_decision"


DECISION_KINDS = tuple(k for k in PublicationKind if k is not PublicationKind.NOT_A_DECISION)

# Dispositive markers are looked for in the end of the text, where a decision rules; the start
# of a monocratic decision often quotes the lower Court's own ementa and sentence.
_TAIL = 2500
_HEAD = 300

_NOT_A_DECISION_LABEL = re.compile(r"edital|pauta|lista de distribuicao|ata de sessao")
_ACORDAO_LABEL = re.compile(r"acordao")
_COMBINED_LABEL = re.compile(r"despacho|decis|sentenca")
_SENTENCA_LABEL = re.compile(r"^\W*sentenca\W*$")
_DESPACHO_LABEL = re.compile(r"^\W*despacho\W*$")

# Boilerplate that only a notice carries.
_NOTICE = re.compile(r"ficam as partes e respectivos representantes cientificados|ato ordinatorio")
# Phrases a notice uses but a decision may contain too: a notice only when nothing rules.
_WEAK_NOTICE = re.compile(
    r"fica(m)? intimad[oa]s?\b|intimacao d[ao] penhora|ciencia as partes|certidao de"
)
_EMENTA = re.compile(r"\bementa\s*:")
_MONOCRATIC = re.compile(
    r"\b(dou (parcial )?provimento|nego (seguimento|provimento)|nao conheco d[eo]"
    r"|conheco d[eo] (agravo|recurso)|nego-lhe provimento|dou-lhe provimento"
    r"|julgo prejudicad[oa]|nao conhecido o recurso)"
)
_SENTENCA = re.compile(
    r"\b(julgo (parcialmente )?(im)?procedentes?|julgo extint[oa]|julga-se|ante o exposto"
    r"|isto posto|condeno|homologo|decreto a|indefiro a (peticao )?inicial|dispositivo)\b"
)
# STJ and the TRFs put a party header before the body, whose first capitalised word names the act.
_ACT_HEADER = re.compile(r"\b(DESPACHO|DECIS[ÃA]O|SENTEN[ÇC]A)\b")
_HEADER_WINDOW = 2000
# A Relator signs a monocratic act at its end: "... Publique-se. Relator JOÃO SILVA".
_RELATOR_SIGNATURE = re.compile(r"\brelatora?\s+(\S+\s+){0,5}\S+\s*$")
_RULING = re.compile(
    r"\b(defiro|indefiro|concedo|nego o pedido|determino|decreto|declaro|fixo|arbitro"
    r"|tutela de urgencia|tutela antecipada|antecipacao de tutela)\b"
)
_DESPACHO_MARKER = re.compile(
    rf"^.{{0,{_HEAD}}}\b(vistos\.|cumpra-se|aguarde-se|int\.|intime-se|manifeste-se|diga|suspendo)"
)


def _fold(value: str | None) -> str:
    """Lower-case and strip the accents, so one pattern covers `SENTENÇA` and `sentenca`."""
    decomposed = unicodedata.normalize("NFKD", (value or "").lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def classify_publication(
    *, communication_type: str | None, document_type: str | None, text: str
) -> PublicationKind:
    """Classify one DJEN item from its `tipoComunicacao`, `tipoDocumento` and plain text."""
    communication = _fold(communication_type)
    label = _fold(document_type)
    body = _fold(text)
    if _NOT_A_DECISION_LABEL.search(communication) or _NOT_A_DECISION_LABEL.search(label):
        return PublicationKind.NOT_A_DECISION
    if _NOTICE.search(body[:_TAIL]) and not _SENTENCA.search(body[-_TAIL:]):
        return PublicationKind.NOT_A_DECISION
    if _ACORDAO_LABEL.search(label):
        return PublicationKind.ACORDAO
    if _DESPACHO_LABEL.search(label):
        return PublicationKind.NOT_A_DECISION
    if _SENTENCA_LABEL.search(label):
        return PublicationKind.SENTENCA
    # A combined label ("DESPACHO / DECISÃO") may quote an ementa without being an acórdão.
    if _EMENTA.search(body) and not _COMBINED_LABEL.search(label):
        return PublicationKind.ACORDAO
    header = _ACT_HEADER.search(text[:_HEADER_WINDOW])
    if header and header.group(1) == "DESPACHO":
        return PublicationKind.NOT_A_DECISION
    tail = body[-_TAIL:]
    if _MONOCRATIC.search(tail) or _RELATOR_SIGNATURE.search(body[-120:]):
        return PublicationKind.DECISAO_MONOCRATICA
    if _SENTENCA.search(tail):
        return PublicationKind.SENTENCA
    return _interlocutory_or_despacho(header, body)


def _interlocutory_or_despacho(header: re.Match[str] | None, body: str) -> PublicationKind:
    if header and header.group(1).startswith("DECIS"):
        return PublicationKind.DECISAO_INTERLOCUTORIA
    ruling = _RULING.search(body)
    despacho = _DESPACHO_MARKER.search(body)
    if ruling and despacho:
        return PublicationKind.AMBIGUOUS
    if ruling:
        return PublicationKind.DECISAO_INTERLOCUTORIA
    if despacho or _WEAK_NOTICE.search(body):
        return PublicationKind.NOT_A_DECISION
    return PublicationKind.AMBIGUOUS
