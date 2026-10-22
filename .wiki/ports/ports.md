---
type: Ports
title: "Ports"
description: "The nine Protocols use cases depend on, and which adapter implements each."
tags: [ports, architecture]
status: stable
generated: { by: claude-code/sonnet-5.5, at: '2026-10-21T00:00:00Z' }
sources:
  - id: p
    resource: juris_bridge_mcp/ports/
    title: ports/
---

# Overview

Ports are `typing.Protocol`s so use cases are tested with fakes, never the network.[^p]

| Port | Contract | Implemented by |
|------|----------|----------------|
| `CaseRepository` | `find(number, court)`, `search(court, filters, limit, after)` | DataJud (+ cache decorator) |
| `PublicationRepository` | `search(PublicationSearch)`; page past the depth ceiling comes back `truncated`; every kind returned, filtering is the caller's | DJEN |
| `PrecedentSource` | `search(filters, page, limit)`, `find(id)`, `decisions(id)`; `find` is `None` when unknown, `decisions` may be empty | BNP (+ cache decorator) |
| `IssuingBodyCatalog` | `version`, `body_ids(court)`; offline | `StaticIssuingBodyCatalog` |
| `LegislationRepository` | `search(filters, limit, offset)`, `find_by_urn` | Senado (+ cache decorator) |
| `NormTextSource` | `fetch(urn)` → `NormText` or `None` | Planalto, Legin, fallback, cache |
| `CoverageCatalog` | `sources()`; never touches the network | `StaticCoverageCatalog` |
| `Cache` | `get`, `set(ttl_seconds)`; miss = `None` | `InMemoryTtlCache` |
| `Limiter` | `acquire()`; waits briefly or raises `rate_limited` | `RateLimiter` |

Concrete adapters: [Sources](/adapters/sources.md), [caching](/architecture/caching.md), [upstream HTTP](/architecture/upstream-http.md).

[^p]: ports/
