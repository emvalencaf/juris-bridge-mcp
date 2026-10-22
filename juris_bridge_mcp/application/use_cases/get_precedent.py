"""Use case: fetch one Precedent by id, with its decisions when the Source has them."""

from dataclasses import dataclass
from datetime import datetime

from juris_bridge_mcp.domain.errors import ToolFailure, not_found
from juris_bridge_mcp.domain.precedent import (
    SOURCE,
    Precedent,
    PrecedentDecisions,
    parse_id,
)
from juris_bridge_mcp.ports.precedent_source import PrecedentSource


@dataclass(frozen=True)
class PrecedentResult:
    """A Precedent ready to present.

    `decisions` is `None` when the Source could not give them; `warnings` says why.
    """

    precedent: Precedent
    decisions: PrecedentDecisions | None
    retrieved_at: datetime
    warnings: tuple[str, ...] = ()


async def get_precedent(source: PrecedentSource, *, precedent_id: str) -> PrecedentResult:
    """Return the Precedent for `precedent_id`.

    Its decisions are fetched on a best-effort basis: a failure there becomes a warning and
    never hides the Precedent.
    """
    key = parse_id(precedent_id)
    record = await source.find(key)
    if record is None:
        raise not_found(
            SOURCE,
            f"No precedent {key}.",
            "Search with search_precedents and pass the id it returns.",
        )
    warnings: list[str] = []
    decisions: PrecedentDecisions | None = None
    try:
        decisions = await source.decisions(key)
    except ToolFailure as failure:
        warnings.append(f"Decisions are unavailable ({failure.code.value}): {failure.message}")
    else:
        if not decisions.texts:
            warnings.append("The Source holds no decision text for this precedent.")
    return PrecedentResult(
        precedent=record.precedent,
        decisions=decisions,
        retrieved_at=record.retrieved_at,
        warnings=tuple(warnings),
    )
