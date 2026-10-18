"""Inbound adapter: the Case tools as a FastMCP sub-server."""

from datetime import date
from typing import Any

from fastmcp import FastMCP

from juris_bridge_mcp.adapters import wide_event
from juris_bridge_mcp.adapters.case_presenter import present_case, present_search
from juris_bridge_mcp.application.use_cases.get_case import (
    DEFAULT_EVENTS_LIMIT,
    get_case,
)
from juris_bridge_mcp.application.use_cases.search_cases import DEFAULT_LIMIT, search_cases
from juris_bridge_mcp.domain.courts import SOURCE
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
            outcome = await get_case(
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
            source=SOURCE,
            court=outcome.case.court,
            result_count=1,
            call_shape={"court_alias": outcome.case.court, "limit": events_limit},
        )
        return present_case(outcome)

    @server.tool(name="search_cases", annotations={"readOnlyHint": True})
    async def search_cases_tool(
        court: str | None = None,
        case_class: int | None = None,
        judging_body: int | None = None,
        subject: int | None = None,
        filed_from: date | None = None,
        filed_to: date | None = None,
        limit: int = DEFAULT_LIMIT,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """Search the Cases (_processos_) of one Brazilian Court by class, judging body,
        subject and filing date.

        `court` is an alias such as `tjsp`, `trf1` or `stj` (see list_coverage); an
        unknown alias returns `invalid_argument` listing the valid ones. It may be left
        out only when `cursor` is passed. `case_class`, `judging_body` and `subject` are
        the numeric official TPU codes (as returned in `class.code`, `judging_body.code`
        and `subjects[].code` by get_case); `filed_from` and `filed_to` are inclusive
        ISO dates (`2024-01-31`). All filters given must match. There are no party,
        judge or CPF filters.

        Returns up to `limit` (1-50, default 10) Cases, oldest update first, each as in
        get_case but without events (call get_case for those), plus `total`. Search
        results are `items`; an empty search returns `items: []`. When more follow,
        `next_cursor` is an opaque token: pass it back with the same court and filters
        to get the next page; it is stateless and stays valid across server restarts.
        The Source counts at most 10,000 matches: then `total_is_lower_bound` is true
        and `hint` says how to narrow the search.
        """
        try:
            outcome = await search_cases(
                repository,
                court=court,
                case_class=case_class,
                judging_body=judging_body,
                subject=subject,
                filed_from=filed_from,
                filed_to=filed_to,
                limit=limit,
                cursor=cursor,
            )
        except ToolFailure as failure:
            wide_event.record_failure(failure)
            raise to_tool_error(failure) from None
        wide_event.annotate(
            source=SOURCE,
            court=outcome.court,
            result_count=len(outcome.cases),
            paginated=cursor is not None,
            call_shape={
                "court_alias": outcome.court,
                "limit": limit,
                "cursor_sent": cursor is not None,
                "filters": [
                    name
                    for name, value in (
                        ("case_class", case_class),
                        ("judging_body", judging_body),
                        ("subject", subject),
                        ("filed_from", filed_from),
                        ("filed_to", filed_to),
                    )
                    if value is not None
                ],
            },
        )
        return present_search(outcome)

    return server
