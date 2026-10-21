"""Maps one DJEN `comunicacao` item to a Publication."""

import re
from datetime import date
from html.parser import HTMLParser
from typing import Any

from juris_bridge_mcp.adapters.schema_drift import SchemaDrift
from juris_bridge_mcp.domain.cnj_number import CnjNumber
from juris_bridge_mcp.domain.publication import Publication
from juris_bridge_mcp.domain.publication_kind import classify_publication

EXCERPT_LENGTH = 500
_DIGITS = re.compile(r"^\d{20}$")
_SKIPPED_TAGS = frozenset({"script", "style"})
# Tags inside a word's line of text; any other tag ends the word before it.
_INLINE_TAGS = frozenset({"a", "b", "i", "u", "em", "strong", "span", "font", "sub", "sup"})


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skipping = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._skipping += tag in _SKIPPED_TAGS
        self._separate(tag)

    def handle_endtag(self, tag: str) -> None:
        self._skipping -= tag in _SKIPPED_TAGS and self._skipping > 0
        self._separate(tag)

    def _separate(self, tag: str) -> None:
        if tag not in _INLINE_TAGS:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if not self._skipping:
            self.parts.append(data)


def plain_text(text: str) -> str:
    """Strip the markup of a published text and collapse its whitespace."""
    extractor = _TextExtractor()
    extractor.feed(text)
    extractor.close()
    return " ".join("".join(extractor.parts).split())


def _excerpt(text: str) -> str:
    if len(text) <= EXCERPT_LENGTH:
        return text
    cut = text[:EXCERPT_LENGTH]
    return cut.rsplit(" ", 1)[0] + "…" if " " in cut else cut + "…"


def _string(item: dict[str, Any], key: str) -> str | None:
    value = item.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise SchemaDrift(f"{key} is not a string")
    return value


def map_publication(item: Any, *, court: str) -> Publication:
    """Map an item, or raise `SchemaDrift` when a field this server needs is not as expected."""
    if not isinstance(item, dict):
        raise SchemaDrift("an item is not an object")
    digits = _string(item, "numero_processo")
    if digits is None or not _DIGITS.match(digits):
        raise SchemaDrift("an item has no 20-digit numero_processo")
    item_hash = _string(item, "hash")
    if not item_hash:
        raise SchemaDrift("an item has no hash")
    released = _string(item, "data_disponibilizacao")
    try:
        day = date.fromisoformat((released or "")[:10])
    except ValueError:
        raise SchemaDrift("an item has no ISO data_disponibilizacao") from None
    text = plain_text(_string(item, "texto") or "")
    document_type = _string(item, "tipoDocumento")
    link = _string(item, "link")
    organ_id = item.get("idOrgao")
    return Publication(
        court=court,
        day=day,
        number=CnjNumber(digits),
        document_type=document_type,
        excerpt=_excerpt(text),
        text_length=len(text),
        item_hash=item_hash,
        kind=classify_publication(
            communication_type=_string(item, "tipoComunicacao"),
            document_type=document_type,
            text=text,
        ),
        url=link if link and link.startswith(("https://", "http://")) else None,
        organ_id=organ_id if isinstance(organ_id, int) and not isinstance(organ_id, bool) else None,
    )
