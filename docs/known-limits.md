# Known limits

Limits you should know before relying on a deployment. The same two limits on
rate limiting and caching are summarised in the README ("Known limits"); this
page explains them.

## Rate limit is per instance

The server limits its calls to each Source with an in-memory limiter: DataJud at
most 120 requests per minute (the figure in the DataJud terms of use, clause
3.13) and the Senado API well under 10 requests per second. After 2 jittered
retries on 429 or 503, a call that would wait longer than about 5 seconds returns
`rate_limited` with `retry_after_seconds` instead of blocking.

The limiter lives in the memory of one process, so it is per instance, not
global. On the Reference deployment (Lambda), each warm execution environment
counts on its own, and Lambda can run several at once. Together they can exceed
a Source's limit even though each stays under it. Do not assume a global
guarantee, and keep the number of concurrent clients low. You
remain responsible for your total volume towards DataJud, see
[RESPONSIBLE_USE.md](../RESPONSIBLE_USE.md).

## Cache is per warm environment

Repeated lookups are served from an in-memory TTL cache behind the `Cache` port
(TTLs and sizes are in `.env.example`). On Lambda the cache lives only as long
as, and only inside, one warm execution environment:

- it is empty after a cold start;
- it is not shared between environments, so a request that lands on another
  instance misses even if a previous identical one hit;
- hit rates therefore depend on traffic: low and bursty traffic sees few hits.

The cache is never persisted, which also keeps DataJud-derived data from being
stored (see [RESPONSIBLE_USE.md](../RESPONSIBLE_USE.md)). A distributed cache is
out of scope for the MVP and can replace the in-memory one behind the port
without changing use cases.

## Other limits

Limits of the norm text (revoked and superseded flags, article boundaries,
Planalto page paths, the Câmara Legin fallback) are listed in the README under
"Known limits".
