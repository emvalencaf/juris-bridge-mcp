---
type: MCP Tool
title: "search_publications"
description: "Search a Court's DJEN Publications by release window and text, or list one Case's Publications."
resource: https://github.com/emvalencaf/juris-bridge-mcp/blob/development/juris_bridge_mcp/adapters/publications/publications_mcp_tools.py
tags: [tool, publications, djen, pagination]
status: stable
generated: { by: claude-code/sonnet-5.5, at: '2026-10-21T00:00:00Z' }
sources:
  - id: t
    resource: juris_bridge_mcp/adapters/publications/publications_mcp_tools.py
    title: publications_mcp_tools.py
  - id: uc
    resource: juris_bridge_mcp/application/use_cases/search_publications.py
    title: search_publications.py
  - id: adr6
    resource: docs/adr/0006-djen-publications-self-hosted.md
    title: ADR 0006
---

# Signature

`search_publications(date_from, date_to, court=None, query=None, cnj_number=None, kind=None, limit=10, cursor=None)`.[^t] `limit` 1–25; window at most 31 days counting both ends.[^uc]

Publications carry personal data (party names); the tool description warns agents about the LGPD.

# Two modes

* **Text search** — `court` and `query` required. The DJEN reads `texto` as one ordered adjacent phrase and ignores operators, so the query is parsed locally ([query syntax](/domain/publication-model.md#query-syntax)). Results are united across OR groups without duplicates.
* **One Case** — `cnj_number` given; `court` derived from it (a mismatch is `invalid_argument`); `query` optional and filters locally. Costs one request however long the window.

`kind` keeps one of `acordao`, `sentenca`, `decisao_monocratica`, `decisao_interlocutoria`, `ambiguous`; by default every decision, ambiguous included.

# Completeness

The Source has no read-by-id, no server-side kind filter and a depth ceiling, so the use case fans out over court, day and Issuing body, bounded to 10 requests per call (`MAX_REQUESTS_PER_CALL`).[^adr6] Results state `complete` or an `incomplete_reason`:

| Reason | Meaning |
|--------|---------|
| `budget` | request budget spent; `next_cursor` reads on |
| `slice_cap` | a day reached the 10,000 count cap and was split by [Issuing body](/decisions/adrs.md#adr-0007); a body slice still capped or a body is missing from the catalog |
| `depth_ceiling` | the Source stops after about `MAX_DJEN_PAGE*100` matches of a slice |

Each page carries a per-page `relevance` (score + matched terms) — see [ranking](/domain/publication-model.md#relevance). STF and electoral Courts, and windows ending before a Court's DJEN start, are `not_covered`. Companion: [get_publication](/tools/get-publication.md).

[^t]: publications_mcp_tools.py
[^uc]: search_publications.py
[^adr6]: ADR 0006
