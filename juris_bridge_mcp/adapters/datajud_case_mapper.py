"""Maps a DataJud `_source` document to a Case; any unexpected shape raises `SchemaDrift`.

DataJud is in beta and already deviates from its own glossary (compact filing dates,
codes that are numbers in one place and strings in another), so every field is checked.
"""

from datetime import UTC, date, datetime
from typing import Any

from juris_bridge_mcp.domain.case import Case, CaseEvent, CodedTerm, EventComplement
from juris_bridge_mcp.domain.cnj_number import CnjNumber


class SchemaDrift(Exception):  # noqa: N818 - names the situation, not an error class
    """The upstream document no longer matches the shape this mapper expects."""


def map_case(source: dict[str, Any], *, number: CnjNumber, court: str) -> Case:
    """Build the Case for `number` from one `_source` document."""
    if source.get("numeroProcesso") != number.digits:
        raise SchemaDrift("numeroProcesso missing or different from the one requested")
    return Case(
        number=number,
        court=court,
        instance=_text(source, "grau"),
        filed_on=_filing_date(source.get("dataAjuizamento")),
        case_class=_term(source.get("classe")),
        subjects=tuple(_required_term(t) for t in _items(source, "assuntos")),
        judging_body=_term(source.get("orgaoJulgador")),
        secrecy_level=_code(source.get("nivelSigilo")),
        source_system=_term(source.get("sistema")),
        last_updated_at=_timestamp(source.get("dataHoraUltimaAtualizacao")),
        events=tuple(_event(m) for m in _items(source, "movimentos")),
    )


def _items(source: dict[str, Any], key: str) -> list[Any]:
    value = source.get(key)
    if value is None:
        return []
    if not isinstance(value, list):
        raise SchemaDrift(f"{key} is not a list")
    return value


def _text(source: dict[str, Any], key: str) -> str | None:
    value = source.get(key)
    if value is None or isinstance(value, str):
        return value
    raise SchemaDrift(f"{key} is not text")


def _code(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise SchemaDrift("a code is a boolean")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    raise SchemaDrift(f"a code is neither a number nor digits: {value!r}")


def _term(value: Any) -> CodedTerm | None:
    if value is None:
        return None
    return _required_term(value)


def _required_term(value: Any) -> CodedTerm:
    if not isinstance(value, dict):
        raise SchemaDrift("a coded term is not an object")
    name = value.get("nome")
    if name is not None and not isinstance(name, str):
        raise SchemaDrift("a term name is not text")
    return CodedTerm(code=_code(value.get("codigo")), name=name)


def _event(value: Any) -> CaseEvent:
    if not isinstance(value, dict):
        raise SchemaDrift("a movement is not an object")
    complements = value.get("complementosTabelados")
    if complements is not None and not isinstance(complements, list):
        raise SchemaDrift("complementosTabelados is not a list")
    term = _required_term(value)
    return CaseEvent(
        code=term.code,
        name=term.name,
        occurred_at=_timestamp(value.get("dataHora")),
        judging_body=_term(value.get("orgaoJulgador")),
        complements=tuple(_complement(c) for c in complements or []),
    )


def _complement(value: Any) -> EventComplement:
    if not isinstance(value, dict):
        raise SchemaDrift("a movement complement is not an object")
    term = _required_term(value)
    kind = value.get("descricao")
    detail = value.get("valor")
    if kind is not None and not isinstance(kind, str):
        raise SchemaDrift("a complement description is not text")
    if detail is not None and not isinstance(detail, int | str):
        raise SchemaDrift("a complement value is not a number or text")
    return EventComplement(code=term.code, name=term.name, kind=kind, value=detail)


def _timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise SchemaDrift("a timestamp is not text")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise SchemaDrift(f"unreadable timestamp: {value!r}") from None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _filing_date(value: Any) -> date | None:
    """DataJud returns the filing date compact (`20181029000000`); accept ISO as well."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise SchemaDrift("dataAjuizamento is not text")
    if len(value) == 14 and value.isdigit():
        try:
            return datetime.strptime(value, "%Y%m%d%H%M%S").date()
        except ValueError:
            raise SchemaDrift(f"unreadable filing date: {value!r}") from None
    parsed = _timestamp(value)
    return parsed.date() if parsed else None
