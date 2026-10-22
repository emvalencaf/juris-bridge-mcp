"""Use case: fetch one federal Norm by URN Lex."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from juris_bridge_mcp.application.use_cases.legislation.norm_text_slice import (
    TextSlice,
    slice_norm_text,
)
from juris_bridge_mcp.domain.errors import invalid_argument, not_found
from juris_bridge_mcp.domain.legislation import SOURCE, Norm, Publication, Relation, Urn
from juris_bridge_mcp.domain.legislation_text import DEFAULT_MAX_CHARS, MAX_MAX_CHARS, article_key
from juris_bridge_mcp.domain.raw_payload import bounded_raw
from juris_bridge_mcp.ports.legislation_repository import LegislationRepository
from juris_bridge_mcp.ports.norm_text_source import NormTextSource

DEFAULT_RELATIONS_LIMIT = 25
MAX_RELATIONS_LIMIT = 100


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
    include_annotations: bool = True,
    relations_limit: int = DEFAULT_RELATIONS_LIMIT,
    include_raw: bool = False,
) -> NormResult:
    """Return the Norm identified by `urn` with its publications and its latest relations.

    Relations are counted once per (related norm, kind) and the most recent `relations_limit`
    are kept, newest first. With `include_text` or an `article`, also a slice of at most
    `max_chars` of the plain text (or of that article); `text_cursor` continues a slice. Without
    `include_annotations` the Annotations are removed from the text first.
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
        raise not_found(
            SOURCE,
            f"No norm {parsed.text} in the Senado catalogue.",
            "Check the urn, or locate the norm with search_legislation.",
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
        text, text_warnings = await slice_norm_text(
            text_source,
            parsed,
            article=key,
            max_chars=max_chars,
            cursor=text_cursor,
            include_annotations=include_annotations,
        )
        warnings.extend(text_warnings)
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
