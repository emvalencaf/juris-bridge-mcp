---
type: MCP Tool
title: "get_legislation"
description: "Fetch a federal Norm by URN Lex, optionally its text or a single article."
resource: https://github.com/emvalencaf/juris-bridge-mcp/blob/development/juris_bridge_mcp/adapters/legislation/legislation_mcp_tools.py
tags: [tool, legislation, senado, planalto]
status: stable
generated: { by: claude-code/sonnet-5.5, at: '2026-10-21T00:00:00Z' }
sources:
  - id: t
    resource: juris_bridge_mcp/adapters/legislation/legislation_mcp_tools.py
    title: legislation_mcp_tools.py
  - id: slice
    resource: juris_bridge_mcp/application/use_cases/legislation/norm_text_slice.py
    title: norm_text_slice.py
---

# Signature

`get_legislation(urn, include_text=False, article=None, max_chars=20000, text_cursor=None, include_annotations=True, relations_limit=25, include_raw=False)`.[^t]

# Metadata (default, Content kind `metadata`)

Type, number, year, signature date, `name`, `nickname`, `summary`, Citation, `publications` (Diário edition/page/column) and `relations` — later norms that amend, regulate, veto or relate to this one. Relations are collapsed to one per norm and kind, newest first, cut to `relations_limit` (1–100) with `relations_total`. Unknown URN → `not_found`.

# Text (`include_text`, Content kind `full_text`)

* Text comes from the Planalto; on `source_blocked`, `source_unavailable` or `rate_limited` it falls back to Câmara Legin and a `warnings` entry says so, with `text_source` named ([sources](/adapters/sources.md)). Both failing raises the Planalto failure; `source_changed` is never masked by the fallback.
* Sliced to `max_chars` (1–100000); when `truncated`, pass `next_text_cursor` back as `text_cursor`.[^slice]
* `article` (`Art. 5º`, `121-A`, `Art. único`) returns only that article with `flags`: `revoked` or `superseded` (struck through). An unlocatable article is `not_found`, never another one. See [article model](/domain/legislation-model.md#articles-and-annotations).
* `include_annotations=false` strips legislative-history notes (`Redação dada...`, `Incluído...`, `Vide...`) to save tokens; `(Revogado ...)` always stays.

[^t]: legislation_mcp_tools.py
[^slice]: norm_text_slice.py
