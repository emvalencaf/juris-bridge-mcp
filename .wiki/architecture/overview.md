---
type: Architecture
title: "Architecture overview"
description: "Layered hexagonal layout of the juris_bridge_mcp package and how a tool call flows through it."
resource: https://github.com/emvalencaf/juris-bridge-mcp/blob/development/juris_bridge_mcp/
tags: [architecture, layers]
status: stable
generated: { by: claude-code/sonnet-5.5, at: '2026-10-21T00:00:00Z' }
sources:
  - id: pkg
    resource: docs/adr/0005-layers-at-the-top.md
    title: ADR 0005 — layers at the top
  - id: boot
    resource: juris_bridge_mcp/infrastructure/bootstrap.py
    title: Composition root
---

# Overview

`juris_bridge_mcp` is an MCP server that gives AI agents one normalized interface to Brazilian judicial and legal data. The layers sit directly under the package (ADR 0005).[^pkg]

| Layer | Folder | Holds |
|-------|--------|-------|
| Domain | `domain/` | Pure types and rules: [CNJ number and Courts](/domain/cnj-number-and-courts.md), [Error codes](/domain/errors.md), [Cursor](/domain/cursor.md), [Publication model](/domain/publication-model.md), [Legislation model](/domain/legislation-model.md). |
| Ports | `ports/` | `Protocol`s the use cases depend on — see [Ports](/ports/ports.md). |
| Application | `application/use_cases/` | One use case per tool operation; depend only on ports and domain. |
| Adapters | `adapters/` | Inbound: FastMCP [tools](/tools/index.md), [Bearer auth](/architecture/request-pipeline.md). Outbound: [Sources](/adapters/sources.md), [caches](/architecture/caching.md), [HTTP client](/architecture/upstream-http.md). |
| Infrastructure | `infrastructure/bootstrap.py` | The [composition root](/architecture/composition-root.md). |
| Config | `config/` | Per-concern [settings](/config/settings.md); only `main.py` and `config/` read the environment. |

# Dependency rule

Domain imports nothing from the other layers. Use cases import domain and ports. Adapters implement ports and call use cases. Isolation between concepts (cases, publications, legislation) is a convention — sub-concept folders, no cross-concept imports — not enforced by structure.[^pkg]

# Request flow

1. `main.py` builds the ASGI app ([composition root](/architecture/composition-root.md)).
2. The [request pipeline](/architecture/request-pipeline.md) opens a wide event, then checks the Bearer key.
3. FastMCP routes `tools/call` to a tool function in an inbound adapter.
4. The tool calls a use case, which validates arguments, resolves Courts/Cursors in the domain and calls a port.
5. An outbound adapter reads the Source through the [rate-limited HTTP client](/architecture/upstream-http.md) and maps the answer to domain types.
6. A presenter turns the result into the Normalized result (with `source`, Citation, `retrieved_at`, Content kind).
7. A `ToolFailure` anywhere becomes an MCP error with a closed [Error code](/domain/errors.md).

[^pkg]: ADR 0005 — layers at the top
[^boot]: Composition root
