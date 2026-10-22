---
type: Domain Model
title: "Cursor"
description: "Opaque stateless pagination token shared by searches and text slices."
resource: https://github.com/emvalencaf/juris-bridge-mcp/blob/development/juris_bridge_mcp/domain/cursor.py
tags: [domain, pagination]
status: stable
generated: { by: claude-code/sonnet-5.5, at: '2026-10-21T00:00:00Z' }
sources:
  - id: c
    resource: juris_bridge_mcp/domain/cursor.py
    title: cursor.py
---

# Overview

A `Cursor` holds `scope` (what issued it: a Court alias, or `senado`), `position` (a tuple of ints/strs) and `filters_key`. It encodes as unpadded URL-safe base64 of compact JSON `{c, p, f}`.[^c] Because nothing is stored, a cursor survives restarts and works across Lambda instances.

* `decode(token, scopes)` raises `invalid_argument` for malformed tokens or a scope outside `scopes`.
* `offset()` reads a single non-negative int (legislation); `sort_position()` reads `(int, str)` (cases).
* `filters_key` lets a use case notice the filters changed under the same cursor.
* Publication searches put richer state in it: day, OR group, Issuing body index and catalog `version` ([ADR 0007](/decisions/adrs.md#adr-0007)); a cursor from another catalog version is `invalid_argument`.

Agents must pass `next_cursor` back unchanged with the same filters.

[^c]: cursor.py
