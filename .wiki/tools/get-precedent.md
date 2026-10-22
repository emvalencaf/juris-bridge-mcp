---
type: MCP Tool
title: "get_precedent"
description: "Read one Precedent with its status history, suspensions, leading Cases and decisions."
resource: https://github.com/emvalencaf/juris-bridge-mcp/blob/development/juris_bridge_mcp/adapters/precedents/precedents_mcp_tools.py
tags: [tool, precedents, bnp]
status: stable
generated: { by: claude-code/sonnet-5.5, at: '2026-10-21T00:00:00Z' }
sources:
  - id: t
    resource: juris_bridge_mcp/adapters/precedents/precedents_mcp_tools.py
    title: precedents_mcp_tools.py
  - id: uc
    resource: juris_bridge_mcp/application/use_cases/get_precedent.py
    title: get_precedent.py
  - id: src
    resource: juris_bridge_mcp/adapters/bnp/precedent_source.py
    title: precedent_source.py
---

# Overview

`get_precedent(id)` takes the `id` a [search](/tools/search-precedents.md) returned (`stf-rg-1002`, lowercase `<body>-<kind>-<number>`). A malformed id is `invalid_argument`, an unknown one `not_found`.[^uc] The BNP has no read-by-id endpoint, so the source searches by body, kind and number (cancelled included) and keeps the result whose id matches.[^src]

# Result

The search item fields plus `status_history` (as the Source orders it), `suspensions` (`active`, `started_on`, `description`), `leading_cases` and `decisions`.[^t]

* A leading Case has `raw_number` as given and a `cnj_number` only when it is a valid [CNJ number](/domain/cnj-number-and-courts.md); an STF incident number is not, so it cannot be chained into [get_case](/tools/get-case.md).
* Decisions come from a second request, **best effort**: a failure becomes a `warnings` entry and `decisions` is null; an answer with no text is a warning too. `content_kind` is `full_text` only when a decision text came, else `metadata`.

Linked court documents may carry personal data, so the tool description warns about the LGPD.

[^t]: precedents_mcp_tools.py
[^uc]: get_precedent.py
[^src]: precedent_source.py
