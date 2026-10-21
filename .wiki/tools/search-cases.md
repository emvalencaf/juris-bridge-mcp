---
type: MCP Tool
title: "search_cases"
description: "Search a Court's Cases by TPU class, judging body, subject and filing date."
resource: https://github.com/emvalencaf/juris-bridge-mcp/blob/development/juris_bridge_mcp/adapters/cases/cases_mcp_tools.py
tags: [tool, cases, datajud, pagination]
status: stable
generated: { by: claude-code/sonnet-5.5, at: '2026-10-21T00:00:00Z' }
sources:
  - id: t
    resource: juris_bridge_mcp/adapters/cases/cases_mcp_tools.py
    title: cases_mcp_tools.py
  - id: uc
    resource: juris_bridge_mcp/application/use_cases/search_cases.py
    title: search_cases.py
---

# Signature

`search_cases(court, case_class, judging_body, subject, filed_from, filed_to, limit=10, cursor=None)`.[^t]

* `court` is required unless `cursor` is passed; an unknown alias is `invalid_argument` listing valid ones.
* `case_class`, `judging_body`, `subject` are numeric TPU codes (as returned by [get_case](/tools/get-case.md)); dates are inclusive. All filters must match. No party, judge or CPF filters.
* `limit` 1–50. Order is oldest update first, stable.

# Pagination

`next_cursor` is an opaque stateless [Cursor](/domain/cursor.md) carrying the Source sort position `(int, str)` and a fingerprint of the filters (`CaseFilters.key`).[^uc] DataJud counts at most 10,000 matches; then `total_is_lower_bound` is true and `hint` says how to narrow.

[^t]: cases_mcp_tools.py
[^uc]: search_cases.py
