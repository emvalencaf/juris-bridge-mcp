---
type: Module
title: "Composition root"
description: "How main.py and bootstrap.py wire adapters and mount one FastMCP sub-server per concept."
resource: https://github.com/emvalencaf/juris-bridge-mcp/blob/development/juris_bridge_mcp/infrastructure/bootstrap.py
tags: [architecture, bootstrap]
status: stable
generated: { by: claude-code/sonnet-5.5, at: '2026-10-21T00:00:00Z' }
sources:
  - id: boot
    resource: juris_bridge_mcp/infrastructure/bootstrap.py
    title: bootstrap.py
  - id: main
    resource: juris_bridge_mcp/main.py
    title: main.py
---

# Overview

`main()` reads `ServerSettings` and refuses to start unless `JURIS_BRIDGE_SERVER_API_KEYS` holds at least one key.[^main] It prints a responsible-use notice, configures the [wide event](/adapters/wide-event.md) logger, builds the app and runs uvicorn with `access_log=False` (the wide event replaces the access log).

`build_server` creates one `UpstreamClient` per Source (datajud, djen, bnp, senado, planalto, camara_legin), each with its own [rate limiter](/architecture/upstream-http.md), then mounts five FastMCP sub-servers **without a namespace**, so tool names must stay unique across modules:[^boot]

| Sub-server | Tools |
|------------|-------|
| coverage | [list_coverage](/tools/list-coverage.md) |
| cases | [get_case](/tools/get-case.md), [search_cases](/tools/search-cases.md) |
| publications | [search_publications](/tools/search-publications.md), [get_publication](/tools/get-publication.md) |
| precedents | [search_precedents](/tools/search-precedents.md), [get_precedent](/tools/get-precedent.md) |
| legislation | [search_legislation](/tools/search-legislation.md), [get_legislation](/tools/get-legislation.md) |

`build_http_app` serves it at `/mcp`, **stateless with JSON responses** (no session id, no SSE), wrapped by `WideEventMiddleware` (outermost) then `BearerAuthMiddleware`. A `transport` argument replaces the network in tests.

# Wiring of decorators

* Cases: `DatajudCaseRepository` inside `CachedCaseRepository`.
* Legislation: `SenadoLegislationRepository` inside `CachedLegislationRepository`; norm text is `FallbackNormTextSource(Planalto, Legin)` inside `CachedNormTextSource`. See [caching](/architecture/caching.md).
* Precedents: `BnpPrecedentSource` inside `CachedPrecedentSource` (1 hour, 256 entries).
* Publications: `DjenPublicationRepository` plus the `StaticIssuingBodyCatalog`; no cache.

[^boot]: bootstrap.py
[^main]: main.py
