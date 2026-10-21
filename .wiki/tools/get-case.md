---
type: MCP Tool
title: "get_case"
description: "Fetch one Case (processo) by CNJ number from DataJud; metadata and movements only."
resource: https://github.com/emvalencaf/juris-bridge-mcp/blob/development/juris_bridge_mcp/adapters/cases/cases_mcp_tools.py
tags: [tool, cases, datajud]
status: stable
generated: { by: claude-code/sonnet-5.5, at: '2026-10-21T00:00:00Z' }
sources:
  - id: t
    resource: juris_bridge_mcp/adapters/cases/cases_mcp_tools.py
    title: cases_mcp_tools.py
  - id: uc
    resource: juris_bridge_mcp/application/use_cases/get_case.py
    title: get_case.py
---

# Signature

`get_case(number, court=None, events_limit=20, include_raw=False)`, read-only.[^t]

* `number`: formatted `NNNNNNN-DD.AAAA.J.TR.OOOO` or 20 digits; length and check digit are validated before any lookup ([CnjNumber](/domain/cnj-number-and-courts.md)).
* `court`: optional alias; otherwise derived from the `J.TR` digits. Needed e.g. for a superior court holding a number that originated elsewhere. STF → `not_covered`.
* `events_limit`: most recent movements (default 20, max 100), chronological; `events_total` gives the full count.
* `include_raw`: attaches the unstable DataJud document, dropped with a warning if too large.

# Returns

Number, Court, instance, filing date, class, subjects, judging body, secrecy level, source system, last update, `events`. Classes/subjects/movements carry the TPU `code` and untranslated Portuguese `name`. **No parties or judges.** Content kind `metadata`; the Citation has no URL.[^uc]

Backed by [DataJud](/adapters/sources.md). Companion: [search_cases](/tools/search-cases.md).

[^t]: cases_mcp_tools.py
[^uc]: get_case.py
