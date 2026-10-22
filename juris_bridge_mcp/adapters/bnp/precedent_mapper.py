"""Maps one BNP `precedente` to a Precedent."""

import re
from datetime import date, datetime
from html import unescape
from typing import Any

from juris_bridge_mcp.adapters.schema_drift import SchemaDrift
from juris_bridge_mcp.domain.precedent import (
    LeadingCase,
    Precedent,
    PrecedentDecisions,
    StatusEntry,
    Suspension,
)
from juris_bridge_mcp.domain.precedent_bodies import court_for_body

_BREAKS = re.compile(r"<\s*br\s*/?\s*>", re.IGNORECASE)
_TAGS = re.compile(r"<[^>]+>")
_MARKED = re.compile(r"<mark>(.*?)</mark>", re.IGNORECASE | re.DOTALL)


def plain_text(text: str) -> str:
    """Strip the markup of a BNP text, keeping its line breaks and collapsing other spaces."""
    lines = unescape(_TAGS.sub("", _BREAKS.sub("\n", text))).split("\n")
    return "\n".join(line for line in (" ".join(raw.split()) for raw in lines) if line)


def _text(item: dict[str, Any], key: str) -> str | None:
    value = item.get(key)
    if not isinstance(value, str):
        return None
    return plain_text(value) or None


def _br_date(value: Any) -> date | None:
    """Parse the `DD/MM/YYYY` the BNP uses in some fields; anything else reads as unknown."""
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%d/%m/%Y").date()
    except ValueError:
        return None


def _iso_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _moment(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _list(item: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = item.get(key)
    if not isinstance(value, list):
        return []
    return [entry for entry in value if isinstance(entry, dict)]


def _matched_terms(item: dict[str, Any]) -> tuple[str, ...]:
    highlight = item.get("highlight")
    if not isinstance(highlight, dict):
        return ()
    found: dict[str, None] = {}
    for value in highlight.values():
        if isinstance(value, str):
            for term in _MARKED.findall(value):
                found.setdefault(" ".join(term.lower().split()), None)
    return tuple(term for term in found if term)


def _leading_case(entry: dict[str, Any]) -> LeadingCase | None:
    number = entry.get("numero")
    if number is None or str(number).strip() == "":
        return None
    case_class = entry.get("classe")
    link = entry.get("link")
    return LeadingCase.from_raw(
        str(number).strip(),
        case_class=case_class if isinstance(case_class, int) else None,
        url=link if isinstance(link, str) and link else None,
    )


def map_precedent(item: Any) -> Precedent:
    """Map a result of the BNP search; raise `SchemaDrift` when its identity is missing."""
    if not isinstance(item, dict):
        raise SchemaDrift("a result is not an object")
    body, kind, number = item.get("orgao"), item.get("tipo"), item.get("nr")
    if not isinstance(body, str) or not isinstance(kind, str) or number in (None, ""):
        raise SchemaDrift("a result lacks orgao, tipo or nr")
    number = str(number)
    precedent_id = item.get("id")
    if not isinstance(precedent_id, str) or not precedent_id:
        precedent_id = f"{body}-{kind}-{number}".lower()
    return Precedent(
        id=precedent_id,
        body=body,
        court=court_for_body(body),
        kind=kind,
        number=number,
        question=_text(item, "questao"),
        thesis=_text(item, "tese"),
        status=_text(item, "situacao"),
        status_history=tuple(
            StatusEntry(
                status=_text(entry, "situacao") or "",
                recorded_at=_moment(entry.get("dataCriacao")),
                admitted_on=_iso_date(entry.get("dataAdmissao")),
                judged_on=_iso_date(entry.get("dataJulgamento")),
                published_on=_iso_date(entry.get("dataPublicacao")),
            )
            for entry in _list(item, "historico")
        ),
        leading_cases=tuple(
            case for case in map(_leading_case, _list(item, "processosParadigma")) if case
        ),
        suspensions=tuple(
            Suspension(
                active=entry["ativa"] if isinstance(entry.get("ativa"), bool) else None,
                started_on=_br_date(entry.get("dataSuspensao")),
                description=_text(entry, "descricao"),
            )
            for entry in _list(item, "suspensoes")
        ),
        updated_on=_br_date(item.get("ultimaAtualizacao")),
        matched_terms=_matched_terms(item),
    )


def map_decisions(body: Any) -> PrecedentDecisions:
    """Map the answer of the decisions endpoint; raise `SchemaDrift` on an unknown text shape."""
    if not isinstance(body, dict):
        raise SchemaDrift("the decisions are not an object")
    texts: list[str] = []
    for entry in body.get("textos") or []:
        if isinstance(entry, str):
            raw = entry
        elif isinstance(entry, dict) and isinstance(entry.get("texto"), str):
            raw = entry["texto"]
        else:
            raise SchemaDrift("a decision text is in an unknown shape")
        if text := plain_text(raw):
            texts.append(text)
    reporter, link = body.get("relator"), body.get("linkAcompanhamentoProcesssual")
    return PrecedentDecisions(
        reporter=reporter if isinstance(reporter, str) and reporter else None,
        tracking_url=link if isinstance(link, str) and link else None,
        texts=tuple(texts),
    )
