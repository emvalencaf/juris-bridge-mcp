---
type: MCP Tool
title: "list_coverage"
description: "States what the server can and cannot answer, by Source and Court, with no network call."
resource: https://github.com/emvalencaf/juris-bridge-mcp/blob/development/juris_bridge_mcp/adapters/coverage_mcp_tools.py
tags: [tool, coverage]
status: stable
generated: { by: claude-code/sonnet-5.5, at: '2026-10-21T00:00:00Z' }
sources:
  - id: t
    resource: juris_bridge_mcp/adapters/coverage_mcp_tools.py
    title: coverage_mcp_tools.py
  - id: cat
    resource: juris_bridge_mcp/adapters/static_coverage_catalog.py
    title: static_coverage_catalog.py
---

# Overview

Returns the Coverage of three Sources, declared in code by `StaticCoverageCatalog`:[^cat]

| Source | Kind | Courts |
|--------|------|--------|
| `datajud` | cases | every DataJud alias; `stf` listed as unsupported ("Not published by DataJud") |
| `djen` | publications | DJEN Courts with `available_from` (first day with data seen); non-DJEN Courts unsupported with a reason |
| `senado` | legislation | no per-Court list |

Each Court row: `alias`, `supported`, `citation_url`, and optional `available_from` and `reason`. Agents should call it before choosing a `court` alias. Defined in [Domain: Coverage and Courts](/domain/cnj-number-and-courts.md).[^t]

[^t]: coverage_mcp_tools.py
[^cat]: static_coverage_catalog.py
