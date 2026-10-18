"""Slices the text of a Norm, or one of its articles, into pieces an agent can page through."""

from dataclasses import dataclass

from juris_bridge_mcp.domain.cursor import Cursor
from juris_bridge_mcp.domain.errors import invalid_argument, not_found
from juris_bridge_mcp.domain.legislation import SOURCE, Urn
from juris_bridge_mcp.domain.legislation_text import (
    TEXT_SOURCE,
    Article,
    NormText,
    article_label,
    strip_annotations,
)
from juris_bridge_mcp.ports.norm_text_source import NormTextSource

_ANNOTATIONS_OMITTED = (
    "Annotations (legislative-history notes) were omitted; pass include_annotations=true "
    "to read them."
)


@dataclass(frozen=True)
class TextSlice:
    """A piece of a norm's plain text, or of one of its articles.

    `next_cursor` is set when `truncated`: pass it back to read the rest.
    """

    text: str
    truncated: bool
    next_cursor: str | None
    url: str
    source: str = TEXT_SOURCE
    article: Article | None = None


async def slice_norm_text(
    text_source: NormTextSource,
    urn: Urn,
    *,
    article: str | None,
    max_chars: int,
    cursor: str | None,
    include_annotations: bool = True,
) -> tuple[TextSlice | None, tuple[str, ...]]:
    """Return the slice and the warnings about it; no slice when the Source has no text page.

    `article` is a key from `article_key`. Without `include_annotations` the text is sliced after
    its Annotations are removed. A `cursor` must come with the same urn, article and
    `include_annotations` it was issued for.
    """
    warnings: list[str] = []
    scope = f"{urn.text}|{article or ''}|{int(include_annotations)}"
    offset = _offset(cursor, scope)
    source_text = await text_source.fetch(urn)
    if source_text is None:
        warnings.append(
            "Neither the Planalto nor the Câmara Legin has a text page this server can locate "
            "for this norm; only metadata is returned."
        )
        return None, tuple(warnings)
    warnings.extend(source_text.warnings)
    chosen = _find_article(source_text, article, urn, warnings) if article is not None else None
    body = chosen.text if chosen is not None else source_text.text
    if not include_annotations:
        plain = strip_annotations(body)
        if plain != body:
            warnings.append(_ANNOTATIONS_OMITTED)
        body = plain
    if offset > 0 and offset >= len(body):
        raise invalid_argument("The cursor is not valid.")
    end = offset + max_chars
    truncated = end < len(body)
    next_cursor = Cursor(SOURCE, (end,), scope).encode() if truncated else None
    piece = TextSlice(
        body[offset:end], truncated, next_cursor, source_text.url, source_text.source, chosen
    )
    return piece, tuple(warnings)


def _offset(cursor: str | None, scope: str) -> int:
    if cursor is None:
        return 0
    decoded = Cursor.decode(cursor, scopes=(SOURCE,))
    if decoded.filters_key != scope:
        raise invalid_argument(
            "The cursor was issued for a different norm or article.",
            hint=(
                "Repeat the same urn, article and include_annotations, "
                "or start again without a cursor."
            ),
        )
    return decoded.offset()


def _find_article(text: NormText, key: str, urn: Urn, warnings: list[str]) -> Article:
    found, occurrences = text.find_article(key)
    if found is None:
        raise not_found(
            text.source,
            f"The parser could not locate {article_label(key)} in the {text.source} text of "
            f"{urn.text}.",
            "The article may not exist or may be laid out in a way this server cannot "
            "read; call again with include_text to read the norm text.",
        )
    if occurrences > 1:
        warnings.append(
            f"{found.label} appears {occurrences} times in the {text.source} text (old wordings "
            "may be kept struck through); the first current one is returned."
        )
    return found
