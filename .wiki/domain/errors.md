---
type: Domain Model
title: "Error codes and ToolFailure"
description: "The closed set of eight Error codes and the MCP error shape every failure uses."
resource: https://github.com/emvalencaf/juris-bridge-mcp/blob/development/juris_bridge_mcp/domain/errors.py
tags: [domain, errors]
status: stable
generated: { by: claude-code/sonnet-5.5, at: '2026-10-21T00:00:00Z' }
sources:
  - id: e
    resource: juris_bridge_mcp/domain/errors.py
    title: errors.py
---

# Error codes

| Code | Meaning | Typical retry |
|------|---------|---------------|
| `invalid_argument` | bad input; names no Source | no |
| `not_found` | Source holds nothing for the item | no |
| `not_covered` | Court/Source outside [Coverage](/tools/list-coverage.md) | no |
| `rate_limited` | local limiter or Source 429; carries `retry_after_seconds` | yes |
| `source_unavailable` | Source down (e.g. 503) | yes |
| `source_auth_failed` | Source rejected the credentials | no |
| `source_changed` | Source answered in an unknown shape (`SchemaDrift`); do not trust partial data | no |
| `source_blocked` | Source refuses the server (challenge/WAF); never circumvented | no |

# ToolFailure

Adapters and use cases raise `ToolFailure(code, message, source, retryable, retry_after_seconds?, hint?)`. `to_tool_error` serialises its payload as JSON text in a FastMCP `ToolError` (`isError: true`), so an agent branches on `code`.[^e] Helper builders: `rate_limited`, `invalid_argument`, `not_found`, `not_covered`, `source_failure`, `source_changed`. Only the code and retryability reach the [wide event](/adapters/wide-event.md), never the message.

[^e]: errors.py
