---
type: Configuration
title: "Settings and environment variables"
description: "Per-concern pydantic settings classes and their environment prefixes and defaults."
tags: [config, env]
status: stable
generated: { by: claude-code/sonnet-5.5, at: '2026-10-21T00:00:00Z' }
sources:
  - id: cfg
    resource: juris_bridge_mcp/config/
    title: config/
---

# Overview

Each class extends `EnvSettings` (extra ignored) and reads one prefix.[^cfg] Only `main.py` and `config/` touch the environment.

| Prefix | Key settings (default) |
|--------|------------------------|
| `JURIS_BRIDGE_SERVER_` | `api_keys` (**required**, comma-separated, trimmed), `host` 0.0.0.0, `port` 8000 |
| `JURIS_BRIDGE_DATAJUD_` | `base_url`, `api_key` (user's own, secret), timeout 20 s, 120 req/min, cache TTL 300 s |
| `JURIS_BRIDGE_DJEN_` | `base_url`, timeout 20 s, **15 req/min** (DJEN allows ~20 per IP in an undocumented window) |
| `JURIS_BRIDGE_SENADO_` | timeout 20 s, 300 req/min (429 above 10 req/s), cache 300 s / 64 entries |
| `JURIS_BRIDGE_PLANALTO_` | timeout 30 s, 60 req/min, cache 3600 s / 16 entries |
| `JURIS_BRIDGE_LEGIN_` | `lexml_base_url`, timeout 30 s, 12 req/min (LexML asks a 5 s crawl delay; a norm costs three requests) |
| `JURIS_BRIDGE_HTTP_` | shared: timeout 15 s, `max_retries` 2, `max_wait_seconds` 5 |
| `JURIS_BRIDGE_LOG_` | `service`, `version`, `commit_hash`, `region` (also `AWS_REGION`) |

The server refuses to start with no API key. Used by the [composition root](/architecture/composition-root.md).

[^cfg]: config/
