---
type: Module
title: "Upstream HTTP client and rate limiter"
description: "Single outbound HTTP path: honest User-Agent, per-Source sliding-window limiter, bounded retries."
resource: https://github.com/emvalencaf/juris-bridge-mcp/blob/development/juris_bridge_mcp/adapters/http_client.py
tags: [architecture, http, rate-limit]
status: stable
generated: { by: claude-code/sonnet-5.5, at: '2026-10-21T00:00:00Z' }
sources:
  - id: http
    resource: juris_bridge_mcp/adapters/http_client.py
    title: http_client.py
  - id: rl
    resource: juris_bridge_mcp/adapters/rate_limiter.py
    title: rate_limiter.py
  - id: pf
    resource: juris_bridge_mcp/adapters/page_fetch.py
    title: page_fetch.py
---

# UpstreamClient

Every Source call goes through `UpstreamClient`.[^http] Per attempt it takes a limiter slot, sends the request and retries statuses in `retried_statuses` (default 429 and 503), with exponential backoff and jitter or the numeric `Retry-After`. Total waiting is capped by `max_wait_seconds`. When exhausted: 429 → retryable `rate_limited` (with `retry_after_seconds`), 503 → retryable `source_unavailable`. Each call records an entry in the wide event's `upstream` list.

The client identifies itself honestly with a User-Agent naming the project and its repository; it never spoofs a browser (ADR 0002). DJEN passes its own `RETRIED_STATUSES` because it wants a long wait after a 429 and handles it itself.

# RateLimiter

A per-instance sliding window (`max_requests` per 60 s) per Source.[^rl] It sleeps up to `max_wait_seconds`; if the slot is further away it raises `rate_limited` instead of hanging the agent. State is per warm environment, so aggregate rate across Lambda instances can exceed the limit.

# page_fetch

`get_page` fetches one static page and turns every unexpected answer into a [ToolFailure](/domain/errors.md); it returns `None` when the Source has no page.[^pf]

Per-Source limits are in [settings](/config/settings.md).

[^http]: http_client.py
[^rl]: rate_limiter.py
[^pf]: page_fetch.py
