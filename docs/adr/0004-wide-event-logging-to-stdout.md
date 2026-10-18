# One wide event per request, as JSON on stdout

Every HTTP request emits exactly one structured log line (a wide event, or
canonical log line) as JSON on stdout, built in a `contextvar` and emitted in
the `finally` of an ASGI middleware. Handlers and tools only add business
context. There is one logger, configured at startup, standard library only, with
two levels (`info`, `error`). Nothing in the app imports CloudWatch or EMF: JSON
on stdout is the observability counterpart of the portability boundary in ADR
0003 ("the container plus environment variables").

The event carries:

- **Environment (every event):** `service`, `version`, `commit_hash`, `region`,
  `cold_start`, `request_id` (the AWS one, falling back to a uuid).
- **Request:** `http.method`, `http.status`, `mcp.method`, `tool.name`,
  `outcome` (`success`, `error`, `unauthorized`, `rate_limited`), `duration_ms`.
- **Tool business context:** `source`, `court`, `result_count`, `cache`
  (`hit`/`miss`), `paginated`, `error.code` (one of the closed set of 8),
  `error.retryable`.
- **Upstream:** a short list `upstream: [{source, status, duration_ms, retries}]`
  inside the same event, never separate lines.
- **Caller:** `caller.key_id` (first 8 hex of the SHA-256 of the API key, absent
  on an invalid or missing key) and `user_agent`.

Never logged, in line with the responsible-use decision: search text, CNJ case
numbers (not even hashed, they are enumerable), party names, `include_raw`
content, response payloads and upstream error bodies. Only the shape of a call
is logged: filter names present, `limit`, whether a cursor was sent, the derived
court alias, the norm type and year. A legislation URN is public and may be
logged.

On AWS, usage and performance are read with CloudWatch Logs Insights over this
JSON (tool counts, `pct(duration_ms, 95)`, error rate by `error.code`). Terraform
provisions the log group with a short retention (30 days) and the saved queries.
There is no sampling, because traffic is low.

## Considered

- **One line per step (request, upstream call, cache):** scatters context and
  forces joins on `request_id` to answer a single question.
- **EMF metrics and alarms in the MVP:** couples the log format to AWS and adds
  custom-metric cost. Metric filters over the same JSON can add them later with
  no app change.
- **Hashing CNJ numbers or search text for correlation:** low-entropy inputs are
  enumerable, so a hash is not anonymisation.
- **A logging port with a CloudWatch adapter:** stdout already is the boundary,
  so the port would add nothing.

## Consequences

Metrics, alarms and tracing are follow-ups that read the same events. Because
`key_id` is derived from the key, rotating a key changes the caller identity in
historical queries.
