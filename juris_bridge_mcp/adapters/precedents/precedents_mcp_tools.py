"""Inbound adapter: the Precedent tools as a FastMCP sub-server."""

from datetime import date
from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from juris_bridge_mcp.adapters import wide_event
from juris_bridge_mcp.adapters.precedents.precedent_presenter import (
    present_precedent,
    present_search,
)
from juris_bridge_mcp.application.use_cases.get_precedent import get_precedent
from juris_bridge_mcp.application.use_cases.search_precedents import (
    DEFAULT_LIMIT,
    search_precedents,
)
from juris_bridge_mcp.domain.errors import ToolFailure, to_tool_error
from juris_bridge_mcp.domain.precedent import SOURCE
from juris_bridge_mcp.ports.precedent_source import PrecedentSource


def _reported(failure: ToolFailure) -> ToolError:
    """Record the failure on the wide event and return the MCP error to raise."""
    wide_event.record_failure(failure)
    return to_tool_error(failure)


def build_precedents_server(source: PrecedentSource) -> FastMCP:
    """Build the sub-server exposing the Precedent tools over the source."""
    server = FastMCP("precedents")

    @server.tool(name="search_precedents", annotations={"readOnlyHint": True})
    async def search_precedents_tool(
        query: str | None = None,
        court: str | None = None,
        kind: str | None = None,
        number: str | None = None,
        updated_from: date | None = None,
        updated_to: date | None = None,
        include_cancelled: bool = False,
        limit: int = DEFAULT_LIMIT,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """Search the Precedents (súmulas, repercussão geral themes, repetitive appeals, IRDRs,
        IACs and similar) of the Banco Nacional de Precedentes (BNP, CNJ).

        A Precedent is a record that fixes a thesis, with its question, status and leading Cases.
        It is not the text of a ruling (see search_publications) nor a Case (see get_case).

        `query` is passed to the BNP, which matches any of the words by default: `+word` makes a
        word required, `"exact phrase"` keeps words together and `-word` excludes one.
        `court` is an alias such as `stf`, `stj` or `trt4` (see list_coverage); an unknown one is
        `invalid_argument`. `kind` is the BNP sigla: `SUM` (súmula), `SV` (súmula vinculante),
        `RG` (repercussão geral theme), `RR` (STJ repetitive appeal), `IRDR`, `IAC`, `OJ` and the
        others in the error hint of an unknown one. `number` is the Precedent number within its
        body and kind, so `court="stf", kind="RG", number="1002"` finds "Tema 1002". All
        filters are optional and combine with AND. `updated_from` and `updated_to` are inclusive
        ISO dates of the last update. Cancelled Precedents are left out unless `include_cancelled`
        is true.

        Returns up to `limit` (1-50, default 10) Precedents in the Source's own text order. Each
        item has an `id` to pass to get_precedent, `court` (the alias, null for a body with none,
        such as the TNU) and `body` (the BNP sigla), `kind`, `number`, `status` (the Source's own
        text, never normalized), `question`, `thesis` (plain text), `updated_on`, `matched_terms`
        (the query terms the BNP highlighted; there is no score), `content_kind: "metadata"` and
        a `citation` whose `url` opens the Precedent in the BNP's public app.

        `total` is how many matched. The BNP counts no further than 10,000, so `total_is_capped`
        true means "at least"; narrow the search then. Pass `next_cursor` back as `cursor` with
        the same filters and `limit` to read on; the BNP shows no more than 10,000 results, so a
        cursor beyond that is `invalid_argument`. The BNP holds only what courts send it, and
        unevenly: STF and STJ are far fuller than most TJs, so an empty result is not proof that
        no Precedent exists. It is updated about twice a month.
        """
        try:
            outcome = await search_precedents(
                source,
                query=query,
                court=court,
                kind=kind,
                number=number,
                updated_from=updated_from,
                updated_to=updated_to,
                include_cancelled=include_cancelled,
                limit=limit,
                cursor=cursor,
            )
        except ToolFailure as failure:
            raise _reported(failure) from None
        filters = {
            "query": query,
            "court": court,
            "kind": kind,
            "number": number,
            "updated_from": updated_from,
            "updated_to": updated_to,
            "include_cancelled": include_cancelled or None,
        }
        wide_event.annotate(
            source=SOURCE,
            court=court,
            result_count=len(outcome.precedents),
            result_total=outcome.total,
            total_is_capped=outcome.total_is_capped,
            paginated=cursor is not None,
            call_shape={
                "filters": sorted(name for name, value in filters.items() if value),
                "precedent_kind": kind.strip().upper() if kind else None,
                "court_alias": court,
                "limit": limit,
                "cursor_sent": cursor is not None,
            },
        )
        return present_search(outcome)

    @server.tool(name="get_precedent", annotations={"readOnlyHint": True})
    async def get_precedent_tool(id: str) -> dict[str, Any]:
        """Read one Precedent found by search_precedents, with its status history, suspensions,
        leading Cases and, when the BNP has them, its decisions.

        `id` is the one a search item carries (such as `stf-rg-1002`); a malformed one is
        `invalid_argument` and an unknown one is `not_found`.

        Returns the same fields as a search item plus `status_history` (as the Source orders it),
        `suspensions` (`active`, `started_on`, `description`: Cases stayed while the Precedent
        is pending), `leading_cases` and `decisions` (`reporter`, `tracking_url`, `texts`).
        A leading Case has `raw_number` exactly as the BNP gave it, `cnj_number` only when that
        is a valid CNJ number (then call get_case with it; an STF incident number is not one,
        so `cnj_number` is null), its TPU `case_class` and the court `url` when there is one.
        The decisions come from a second request made on a best-effort basis: when it fails or
        holds no text, `decisions` is null or has empty `texts`, `warnings` says why and
        `content_kind` stays `metadata`. It is `full_text` only when a decision text came.
        Linked court documents may carry personal data (party names): the LGPD applies to
        what you do with them.
        """
        try:
            outcome = await get_precedent(source, precedent_id=id)
        except ToolFailure as failure:
            raise _reported(failure) from None
        wide_event.annotate(source=SOURCE, court=outcome.precedent.court, result_count=1)
        return present_precedent(outcome)

    return server
