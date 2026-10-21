---
type: Module
title: "Request pipeline (auth and wide event)"
description: "The two ASGI middlewares every HTTP request passes through, in order."
resource: https://github.com/emvalencaf/juris-bridge-mcp/blob/development/juris_bridge_mcp/adapters/bearer_auth.py
tags: [architecture, auth, logging]
status: stable
generated: { by: claude-code/sonnet-5.5, at: '2026-10-21T00:00:00Z' }
sources:
  - id: auth
    resource: juris_bridge_mcp/adapters/bearer_auth.py
    title: bearer_auth.py
  - id: we
    resource: juris_bridge_mcp/adapters/wide_event_middleware.py
    title: wide_event_middleware.py
  - id: adr4
    resource: docs/adr/0004-wide-event-logging-to-stdout.md
    title: ADR 0004
---

# Order

1. **WideEventMiddleware** (outermost) builds the event around the app and emits it in `finally`, whatever happens.[^we]
2. **BearerAuthMiddleware** answers `401 {"error":"unauthorized"}` with `WWW-Authenticate: Bearer` unless `Authorization: Bearer <key>` matches a configured key.[^auth]

# Auth details

* The token is compared with `hmac.compare_digest` against **every** key, so timing does not reveal which matched.
* On success the caller is recorded as the first 8 hex chars of the SHA-256 of the key (`caller.key_id`); rotating a key changes the caller identity in history.[^adr4]
* Auth lives in the app because a Lambda Function URL offers only `AWS_IAM` or `NONE` (ADR 0003).

See [wide event](/adapters/wide-event.md) for what is logged.

[^auth]: bearer_auth.py
[^we]: wide_event_middleware.py
[^adr4]: ADR 0004
