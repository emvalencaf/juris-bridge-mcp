"""Use case: fetch one federal Norm by URN Lex."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from juris_bridge_mcp.domain.cursor import Cursor
from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure, invalid_argument
from juris_bridge_mcp.domain.legislation import SOURCE, Norm, Publication, Relation, Urn
from juris_bridge_mcp.domain.legislation_text import (
    DEFAULT_MAX_CHARS,
    MAX_MAX_CHARS,
    TEXT_SOURCE,
    Article,
    NormText,
    article_key,
    article_label,
)
from juris_bridge_mcp.domain.raw_payload import bounded_raw
from juris_bridge_mcp.ports.legislation_repository import LegislationRepository
from juris_bridge_mcp.ports.norm_text_source import NormTextSource

DEFAULT_RELATIONS_LIMIT = 25
MAX_RELATIONS_LIMIT = 100


@dataclass(frozen=True)
class TextSlice:
    """A piece of a norm's plain text, or of one of its articles.

    `next_cursor` is set when `truncated`: pass it back to read the rest.
    """

    text: str
    truncated: bool
    next_cursor: str | None
    url: str
    article: Article | None = None


@dataclass(frozen=True)
class NormResult:
    """A Norm ready to present: relations cut to the limit, with what the cut left out.

    `raw` is the unstable upstream payload, present only when asked for and small enough.
    `text` is present only when the text or an article was asked for and the Source had it.
    """

    norm: Norm
    publications: tuple[Publication, ...]
    relations: tuple[Relation, ...]
    relations_total: int
    retrieved_at: datetime
    warnings: tuple[str, ...] = ()
    raw: dict[str, Any] | None = None
    text: TextSlice | None = None


async def get_legislation(
    repository: LegislationRepository,
    text_source: NormTextSource,
    *,
    urn: str,
    include_text: bool = False,
    article: str | None = None,
    max_chars: int = DEFAULT_MAX_CHARS,
    text_cursor: str | None = None,
    relations_limit: int = DEFAULT_RELATIONS_LIMIT,
    include_raw: bool = False,
) -> NormResult:
    """Return the Norm identified by `urn` with its publications and its latest relations.

    Relations are counted once per (related norm, kind) and the most recent `relations_limit`
    are kept, newest first. With `include_text` or an `article`, also a slice of at most
    `max_chars` of the plain text (or of that article); `text_cursor` continues a slice.
    """
    if not 1 <= relations_limit <= MAX_RELATIONS_LIMIT:
        raise invalid_argument(f"relations_limit must be between 1 and {MAX_RELATIONS_LIMIT}.")
    if not 1 <= max_chars <= MAX_MAX_CHARS:
        raise invalid_argument(f"max_chars must be between 1 and {MAX_MAX_CHARS}.")
    parsed = Urn.parse(urn)
    key = article_key(article) if article is not None else None
    wants_text = include_text or key is not None
    if text_cursor is not None and not wants_text:
        raise invalid_argument("text_cursor needs include_text or an article.")
    record = await repository.find_by_urn(parsed)
    if record is None:
        raise ToolFailure(
            ErrorCode.NOT_FOUND,
            f"No norm {parsed.text} in the Senado catalogue.",
            source=SOURCE,
            retryable=False,
            hint="Check the urn, or locate the norm with search_legislation.",
        )
    relations = record.latest_relations()
    warnings: list[str] = []
    raw = None
    if include_raw:
        raw, omitted = bounded_raw(record.raw)
        if omitted:
            warnings.append(omitted)
    text = None
    if wants_text:
        text = await _text_slice(
            text_source, parsed, key, max_chars=max_chars, cursor=text_cursor, warnings=warnings
        )
    return NormResult(
        norm=record.norm,
        publications=record.publications,
        relations=relations[:relations_limit],
        relations_total=len(relations),
        retrieved_at=record.retrieved_at,
        warnings=tuple(warnings),
        raw=raw,
        text=text,
    )


async def _text_slice(
    text_source: NormTextSource,
    urn: Urn,
    key: str | None,
    *,
    max_chars: int,
    cursor: str | None,
    warnings: list[str],
) -> TextSlice | None:
    """Slice the norm text, or one article of it; `None` (and a warning) without a text."""
    scope = f"{urn.text}|{key or ''}"
    offset = _text_offset(cursor, scope)
    source_text = await text_source.fetch(urn)
    if source_text is None:
        warnings.append(
            "The Planalto has no text page this server can locate for this norm; "
            "only metadata is returned."
        )
        return None
    chosen = _article(source_text, key, urn, warnings) if key is not None else None
    body = chosen.text if chosen is not None else source_text.text
    if offset > len(body):
        raise invalid_argument("The cursor is not valid.")
    end = offset + max_chars
    truncated = end < len(body)
    next_cursor = Cursor(SOURCE, (end, 0), scope).encode() if truncated else None
    return TextSlice(body[offset:end], truncated, next_cursor, source_text.url, chosen)


def _text_offset(cursor: str | None, scope: str) -> int:
    if cursor is None:
        return 0
    decoded = Cursor.decode(cursor, scopes=(SOURCE,))
    position = decoded.position[0]
    if decoded.filters_key != scope or isinstance(position, str) or position < 0:
        raise invalid_argument(
            "The cursor was issued for a different norm or article.",
            hint="Repeat the same urn and article, or start again without a cursor.",
        )
    return position


def _article(text: NormText, key: str, urn: Urn, warnings: list[str]) -> Article:
    found, occurrences = text.find_article(key)
    if found is None:
        raise ToolFailure(
            ErrorCode.NOT_FOUND,
            f"The parser could not locate {article_label(key)} in the {TEXT_SOURCE} text of "
            f"{urn.text}.",
            source=TEXT_SOURCE,
            retryable=False,
            hint="The article may not exist or may be laid out in a way this server cannot "
            "read; call again with include_text to read the norm text.",
        )
    if occurrences > 1:
        warnings.append(
            f"{found.label} appears {occurrences} times in the Planalto text (old wordings "
            "are kept struck through); the first current one is returned."
        )
    return found
