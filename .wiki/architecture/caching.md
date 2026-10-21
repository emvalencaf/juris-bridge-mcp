---
type: Module
title: "Caching"
description: "In-memory TTL cache behind the Cache port and the three cache decorators."
resource: https://github.com/emvalencaf/juris-bridge-mcp/blob/development/juris_bridge_mcp/adapters/in_memory_ttl_cache.py
tags: [architecture, cache]
status: stable
generated: { by: claude-code/sonnet-5.5, at: '2026-10-21T00:00:00Z' }
sources:
  - id: c
    resource: juris_bridge_mcp/adapters/in_memory_ttl_cache.py
    title: in_memory_ttl_cache.py
  - id: cl
    resource: juris_bridge_mcp/adapters/senado/cached_legislation_repository.py
    title: cached_legislation_repository.py
---

# Overview

`InMemoryTtlCache` implements the `Cache` port ([ports](/ports/ports.md)); entries live only as long as the warm environment, never shared across Lambda instances or restarts.[^c]

| Decorator | Caches | Notes |
|-----------|--------|-------|
| `CachedCaseRepository` | found Cases | A missing Case is asked again. TTL `cache_ttl_seconds` (300 s). `retrieved_at` stays the time the Source was asked. |
| `CachedLegislationRepository` | the whole match list per filters | Sliced into pages, so paging costs one request.[^cl] 300 s, 64 entries. |
| `CachedNormTextSource` | parsed norm texts | Only found texts. 3600 s, 16 entries because pages weigh megabytes once parsed. |

Publications are not cached: the [Cursor](/domain/cursor.md) is stateless and the search is a time-bounded fan-out.

[^c]: in_memory_ttl_cache.py
[^cl]: cached_legislation_repository.py
