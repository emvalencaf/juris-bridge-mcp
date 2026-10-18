"""Use case: fetch one federal Norm by URN Lex."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure, invalid_argument
from juris_bridge_mcp.domain.legislation import SOURCE, Norm, Publication, Relation, parse_urn
from juris_bridge_mcp.domain.raw_payload import bounded_raw
from juris_bridge_mcp.ports.legislation_repository import LegislationRepository

DEFAULT_RELATIONS_LIMIT = 25
MAX_RELATIONS_LIMIT = 100


@dataclass(frozen=True)
class NormResult:
    """A Norm ready to present: relations cut to the limit, with what the cut left out.

    `raw` is the unstable upstream payload, present only when asked for and small enough.
    """

    norm: Norm
    publications: tuple[Publication, ...]
    relations: tuple[Relation, ...]
    relations_total: int
    retrieved_at: datetime
    warnings: tuple[str, ...] = ()
    raw: dict[str, Any] | None = None


async def get_legislation(
    repository: LegislationRepository,
    *,
    urn: str,
    include_text: bool = False,
    relations_limit: int = DEFAULT_RELATIONS_LIMIT,
    include_raw: bool = False,
) -> NormResult:
    """Return the Norm identified by `urn` with its publications and its latest relations.

    Relations are counted once per (related norm, kind) and the most recent `relations_limit`
    are kept, newest first.
    """
    if not 1 <= relations_limit <= MAX_RELATIONS_LIMIT:
        raise invalid_argument(f"relations_limit must be between 1 and {MAX_RELATIONS_LIMIT}.")
    urn = urn.strip()
    parse_urn(urn)
    if include_text:
        raise ToolFailure(
            ErrorCode.NOT_COVERED,
            "The text of a norm is not available yet.",
            source=SOURCE,
            retryable=False,
            hint="Call again without include_text for the norm's metadata.",
        )
    record = await repository.find(urn)
    if record is None:
        raise ToolFailure(
            ErrorCode.NOT_FOUND,
            f"No norm {urn} in the Senado catalogue.",
            source=SOURCE,
            retryable=False,
            hint="Check the urn, or locate the norm with search_legislation.",
        )
    distinct = {(r.norm_id, r.kind): r for r in record.relations}.values()
    newest_first = sorted(distinct, key=lambda r: r.signed_on or date.min, reverse=True)
    warnings: list[str] = []
    raw = None
    if include_raw:
        raw, omitted = bounded_raw(record.raw)
        if omitted:
            warnings.append(omitted)
    return NormResult(
        norm=record.norm,
        publications=record.publications,
        relations=tuple(newest_first[:relations_limit]),
        relations_total=len(newest_first),
        retrieved_at=record.retrieved_at,
        warnings=tuple(warnings),
        raw=raw,
    )
