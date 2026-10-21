---
type: MCP Tool
title: "search_legislation"
description: "Locate a federal Norm by type, number and year via the Senado API."
resource: https://github.com/emvalencaf/juris-bridge-mcp/blob/development/juris_bridge_mcp/adapters/legislation/legislation_mcp_tools.py
tags: [tool, legislation, senado, pagination]
status: stable
generated: { by: claude-code/sonnet-5.5, at: '2026-10-21T00:00:00Z' }
sources:
  - id: t
    resource: juris_bridge_mcp/adapters/legislation/legislation_mcp_tools.py
    title: legislation_mcp_tools.py
  - id: uc
    resource: juris_bridge_mcp/application/use_cases/legislation/search_legislation.py
    title: search_legislation.py
---

# Signature

`search_legislation(type, number=None, year=None, limit=10, cursor=None)`.[^t]

* `type`: `lei`, `lei-complementar`, `decreto`, `decreto-lei`, `medida-provisoria`, `emenda-constitucional` ([NORM_TYPES](/domain/legislation-model.md)).
* Pass `number`, `year` or both. **No free-text search**; federal norms only.
* `limit` 1–50. Each item has the `urn`, official `name`, `summary` (ementa), signature date and a Citation to the canonical page. Metadata only.

Pagination uses an offset [Cursor](/domain/cursor.md) with scope `senado`; the Senado list is cached whole per filters so pages cost one request ([caching](/architecture/caching.md)).[^uc] Next step: [get_legislation](/tools/get-legislation.md).

[^t]: legislation_mcp_tools.py
[^uc]: search_legislation.py
