"""Maps a DataJud `_source` document to a Case; any unexpected shape raises `SchemaDrift`.

DataJud is in beta and already deviates from its own glossary (compact filing dates,
codes that are numbers in one place and strings in another), so every field is checked.
Timestamps are ISO 8601 with a `Z` in every Court sampled; one without a zone is drift,
not a guess. The filing date is a compact civil date and is kept as the date it states.
"""

from datetime import date, datetime
from typing import Any

from juris_bridge_mcp.adapters.schema_drift import SchemaDrift
from juris_bridge_mcp.domain.case import Case, CaseEvent, CodedTerm, EventComplement
from juris_bridge_mcp.domain.cnj_number import CnjNumber


def map_case(source: dict[str, Any], *, number: CnjNumber, court: str) -> Case:
    """Build the Case for `number` from one `_source` document."""
    if source.get("numeroProcesso") != number.digits:
        raise SchemaDrift("numeroProcesso missing or different from the one requested")
    return Case(
        number=number,
        court=court,
        instance=_expect(source.get("grau"), str, "grau"),
        filed_on=_filing_date(source.get("dataAjuizamento")),
        case_class=_term(source.get("classe")),
        subjects=tuple(_required_term(t) for t in _items(source, "assuntos")),
        judging_body=_term(source.get("orgaoJulgador")),
        secrecy_level=_code(source.get("nivelSigilo")),
        source_system=_term(source.get("sistema")),
        last_updated_at=_timestamp(source.get("dataHoraUltimaAtualizacao")),
        events=tuple(_event(m) for m in _items(source, "movimentos")),
    )


def _expect(value: Any, kind: type | tuple[type, ...], what: str) -> Any:
    """Return `value` when it is absent or of `kind`; anything else is drift."""
    if value is not None and not isinstance(value, kind):
        raise SchemaDrift(f"{what} has an unexpected type")
    return value


def _items(source: dict[str, Any], key: str) -> list[Any]:
    return _expect(source.get(key), list, key) or []


def _code(value: Any) -> int | None:
    if isinstance(value, bool):
        raise SchemaDrift("a code is a boolean")
    if isinstance(value, str) and value.isdigit():
        return int(value)
    result: int | None = _expect(value, int, "a code")
    return result


def _term(value: Any) -> CodedTerm | None:
    return None if value is None else _required_term(value)


def _required_term(value: Any) -> CodedTerm:
    fields: dict[str, Any] = _expect(value, dict, "a coded term")
    if fields is None:
        raise SchemaDrift("a coded term is missing")
    return CodedTerm(
        code=_code(fields.get("codigo")), name=_expect(fields.get("nome"), str, "nome")
    )


def _event(value: Any) -> CaseEvent:
    fields: dict[str, Any] = _expect(value, dict, "a movement")
    if fields is None:
        raise SchemaDrift("a movement is missing")
    return CaseEvent(
        term=_required_term(fields),
        occurred_at=_timestamp(fields.get("dataHora")),
        judging_body=_term(fields.get("orgaoJulgador")),
        complements=tuple(_complement(c) for c in _items(fields, "complementosTabelados")),
    )


def _complement(value: Any) -> EventComplement:
    fields: dict[str, Any] = _expect(value, dict, "a movement complement")
    if fields is None:
        raise SchemaDrift("a movement complement is missing")
    return EventComplement(
        term=_required_term(fields),
        kind=_expect(fields.get("descricao"), str, "descricao"),
        value=_expect(fields.get("valor"), (int, str), "valor"),
    )


def _timestamp(value: Any) -> datetime | None:
    text = _expect(value, str, "a timestamp")
    if text is None:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        raise SchemaDrift(f"unreadable timestamp: {text!r}") from None
    if parsed.tzinfo is None:
        raise SchemaDrift(f"timestamp without a time zone: {text!r}")
    return parsed


def _filing_date(value: Any) -> date | None:
    """DataJud returns the filing date compact (`20181029000000`); accept ISO as well."""
    text = _expect(value, str, "dataAjuizamento")
    if text is None:
        return None
    try:
        if len(text) == 14 and text.isdigit():
            return datetime.strptime(text, "%Y%m%d%H%M%S").date()
        return datetime.fromisoformat(text).date()
    except ValueError:
        raise SchemaDrift(f"unreadable filing date: {text!r}") from None
