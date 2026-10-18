"""Inbound adapter: the Case tools as a FastMCP sub-server."""

from typing import Any

from fastmcp import FastMCP

from juris_bridge_mcp.adapters import wide_event
from juris_bridge_mcp.application.use_cases.get_case import (
    DEFAULT_EVENTS_LIMIT,
    get_case,
)
from juris_bridge_mcp.domain.errors import ToolFailure, to_tool_error
from juris_bridge_mcp.ports.case_repository import CaseRepository


def build_cases_server(repository: CaseRepository) -> FastMCP:
    """Build the sub-server exposing the Case tools over the given repository."""
    server = FastMCP("cases")

    @server.tool(name="get_case", annotations={"readOnlyHint": True})
    async def get_case_tool(
        number: str,
        court: str | None = None,
        events_limit: int = DEFAULT_EVENTS_LIMIT,
        include_raw: bool = False,
    ) -> dict[str, Any]:
        """Fetch one Brazilian court Case (_processo_) by its CNJ number.

        `number` is the unified CNJ number, either `NNNNNNN-DD.AAAA.J.TR.OOOO` or the
        same 20 digits; a wrong length or check digit is rejected without a lookup.
        The Court is derived from the J.TR digits of the number (TRF, TRT, TRE, TJ, TJM
        and the military court STM); pass `court` (an alias such as `tjsp`, see
        list_coverage) to override it, for example when a superior court holds a number
        that originated elsewhere. STF Cases are not published, so they return
        `not_covered`.

        Returns metadata only: number, Court, instance, filing date, class, subjects,
        judging body, secrecy level, source system and last update. There are no
        parties or judges. Classes, subjects and movements carry the official TPU
        `code` and the untranslated Portuguese `name`. `events` are the movements
        (_movimentos_), the most recent `events_limit` (default 20, max 100) in
        chronological order, with `events_total` giving the full count. Dates are
        ISO 8601; absent values are null or []. `include_raw` attaches the upstream
        DataJud document, whose shape is unstable; it is left out if too large.
        """
        try:
            result = await get_case(
                repository,
                number=number,
                court=court,
                events_limit=events_limit,
                include_raw=include_raw,
            )
        except ToolFailure as failure:
            wide_event.record_failure(failure)
            raise to_tool_error(failure) from None
        wide_event.annotate(
            source=result["source"],
            court=result["court"],
            result_count=1,
            call_shape={"court_alias": result["court"], "limit": events_limit},
        )
        return result

    return server
