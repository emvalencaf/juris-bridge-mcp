---
type: Module
title: "Wide event logging"
description: "One JSON log line per request on stdout, built in a contextvar with allow-listed fields."
resource: https://github.com/emvalencaf/juris-bridge-mcp/blob/development/juris_bridge_mcp/adapters/wide_event.py
tags: [adapters, logging, privacy]
status: stable
generated: { by: claude-code/sonnet-5.5, at: '2026-10-21T00:00:00Z' }
sources:
  - id: we
    resource: juris_bridge_mcp/adapters/wide_event.py
    title: wide_event.py
  - id: adr4
    resource: docs/adr/0004-wide-event-logging-to-stdout.md
    title: ADR 0004
---

# Overview

The middleware starts a `WideEvent` in a contextvar; tools add context through helpers (`annotate`, `record_failure`, `record_upstream`, `set_caller`, `annotate_mcp`) and the middleware emits it once in `finally`. Outside a request the helpers are no-ops.[^we] `configure_logger` sends bare JSON lines to stdout (stdlib only, levels `info` and `error`).

Fields: environment (`service`, `version`, `commit_hash`, `region`, `cold_start`, `request_id`), request (`http.*`, `mcp.method`, `tool.name`, `outcome`, `duration_ms`), tool context (`source`, `court`, `result_count`, `cache`, `paginated`, `error.code`, `error.retryable`), `upstream` list, and `caller.key_id`.[^adr4]

# Privacy rule

Helpers take **named, allow-listed fields** so request content has no way in. Never logged: search text, CNJ numbers (even hashed — enumerable), party names, `include_raw` content, payloads, upstream error bodies. Only the shape of a call is logged (filter names, limit, cursor sent, derived court alias). A legislation URN is public and may be logged.

[^we]: wide_event.py
[^adr4]: ADR 0004
