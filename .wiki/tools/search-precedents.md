---
type: MCP Tool
title: "search_precedents"
description: "Search the Precedents (súmulas, themes, repetitive appeals, IRDRs) of the BNP by text, Court, kind, number and update date."
resource: https://github.com/emvalencaf/juris-bridge-mcp/blob/development/juris_bridge_mcp/adapters/precedents/precedents_mcp_tools.py
tags: [tool, precedents, bnp, pagination]
status: stable
generated: { by: claude-code/sonnet-5.5, at: '2026-10-21T00:00:00Z' }
sources:
  - id: t
    resource: juris_bridge_mcp/adapters/precedents/precedents_mcp_tools.py
    title: precedents_mcp_tools.py
  - id: uc
    resource: juris_bridge_mcp/application/use_cases/search_precedents.py
    title: search_precedents.py
  - id: adr8
    resource: docs/adr/0008-bnp-as-the-source-of-precedents.md
    title: ADR 0008
---

# Signature

`search_precedents(query=None, court=None, kind=None, number=None, updated_from=None, updated_to=None, include_cancelled=False, limit=10, cursor=None)`.[^t] `limit` 1–50. Every filter is optional and they combine with AND.[^uc]

# Filters

* `query` goes to the BNP unchanged: any word by default, `+word` required, `"exact phrase"`, `-word` excluded.
* `court` is a Court alias (`stf`, `stj`, `trt4`...), one of the [BNP bodies](/adapters/bnp-source.md#bodies); the TNU has no alias and cannot be filtered. `kind` is a [Precedent kind](/domain/precedent-model.md#kinds) sigla.
* `number` plus `court` and `kind` finds "Tema 1002 do STF" in one call.
* Cancelled Precedents are left out unless `include_cancelled`. `updated_from`/`updated_to` are inclusive ISO dates.

# Result

A Normalized result: `source: "bnp"`, `content_kind: "metadata"`, `total`, `total_is_capped`, `next_cursor` and `items`. Each item has `id` (for [get_precedent](/tools/get-precedent.md)), `court` (null for a body without alias), `body`, `kind`, `number`, the literal `status`, plain-text `question` and `thesis`, `updated_on`, `matched_terms` and a `citation` whose `url` opens the Precedent in the BNP public app. There is no relevance `score` and no per-body count: the BNP gives neither per query.

# Paging and limits

The [Cursor](/domain/cursor.md) carries the 1-based BNP page and a fingerprint of the filters and `limit`; changing either is `invalid_argument`. The BNP counts no further than 10,000, so `total_is_capped` means "at least"; no cursor is offered past that ceiling and a forged one is refused.[^adr8] The BNP holds only what courts send it, so an empty result proves nothing.

[^t]: precedents_mcp_tools.py
[^uc]: search_precedents.py
[^adr8]: ADR 0008
