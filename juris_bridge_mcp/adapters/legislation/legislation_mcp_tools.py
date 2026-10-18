"""Inbound adapter: the Legislation tools as a FastMCP sub-server."""

from typing import Any

from fastmcp import FastMCP

from juris_bridge_mcp.adapters import wide_event
from juris_bridge_mcp.adapters.legislation.legislation_presenter import present_norm, present_search
from juris_bridge_mcp.application.use_cases.get_legislation import (
    DEFAULT_RELATIONS_LIMIT,
    get_legislation,
)
from juris_bridge_mcp.application.use_cases.search_legislation import (
    DEFAULT_LIMIT,
    search_legislation,
)
from juris_bridge_mcp.domain.errors import ToolFailure, to_tool_error
from juris_bridge_mcp.domain.legislation import SOURCE
from juris_bridge_mcp.ports.legislation_repository import LegislationRepository


def build_legislation_server(repository: LegislationRepository) -> FastMCP:
    """Build the sub-server exposing the Legislation tools over the given repository."""
    server = FastMCP("legislation")

    @server.tool(name="search_legislation", annotations={"readOnlyHint": True})
    async def search_legislation_tool(
        type: str,
        number: int | None = None,
        year: int | None = None,
        limit: int = DEFAULT_LIMIT,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """Locate a Brazilian federal norm from a reference such as "Lei 14.133/2021".

        `type` is one of `lei`, `lei-complementar`, `decreto`, `decreto-lei`,
        `medida-provisoria` or `emenda-constitucional`. Pass `number`, `year` or both;
        there is no free-text search. Federal norms only.

        Returns up to `limit` (1-50, default 10) norms in `items`; an empty search
        returns `items: []`. Each item carries the `urn` (URN Lex, for example
        `urn:lex:br:federal:lei:2021-04-01;14133`), the official `name`, `summary`
        (_ementa_), signature date, and a Citation with the canonical page URL. Content
        is metadata only, not the norm text. When more follow, `next_cursor` is an
        opaque token: pass it back with the same type, number and year for the next page.
        """
        try:
            outcome = await search_legislation(
                repository, norm_type=type, number=number, year=year, limit=limit, cursor=cursor
            )
        except ToolFailure as failure:
            wide_event.record_failure(failure)
            raise to_tool_error(failure) from None
        wide_event.annotate(
            source=SOURCE,
            result_count=len(outcome.norms),
            paginated=cursor is not None,
            call_shape={
                "limit": limit,
                "cursor_sent": cursor is not None,
                "filters": [name for name, value in (("number", number), ("year", year)) if value],
            },
        )
        return present_search(outcome)

    @server.tool(name="get_legislation", annotations={"readOnlyHint": True})
    async def get_legislation_tool(
        urn: str,
        include_text: bool = False,
        relations_limit: int = DEFAULT_RELATIONS_LIMIT,
        include_raw: bool = False,
    ) -> dict[str, Any]:
        """Fetch one Brazilian federal norm by its URN Lex (see search_legislation).

        `urn` looks like `urn:lex:br:federal:lei:2021-04-01;14133`. Returns type,
        number, year, signature date, official `name`, `nickname`, `summary` (_ementa_),
        a Citation with the canonical page URL, `publications` (Diário Oficial edition,
        page and column) and `relations`: later norms that amend, regulate, veto or
        relate to this one, each with its `kind` (the Senado's Portuguese label), name
        and date. Heavily amended norms have many, so only the newest `relations_limit`
        (1-100, default 25) are returned, newest first, and `relations_total` gives
        the full count. Content is metadata only: `include_text` is not available yet and
        returns `not_covered`. An unknown URN returns `not_found`. `include_raw` attaches
        the upstream Senado document, whose shape is unstable; it is left out if too large.
        """
        try:
            outcome = await get_legislation(
                repository,
                urn=urn,
                include_text=include_text,
                relations_limit=relations_limit,
                include_raw=include_raw,
            )
        except ToolFailure as failure:
            wide_event.record_failure(failure)
            raise to_tool_error(failure) from None
        wide_event.annotate(
            source=SOURCE,
            result_count=1,
            call_shape={"limit": relations_limit},
        )
        return present_norm(outcome)

    return server
