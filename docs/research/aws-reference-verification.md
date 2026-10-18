# Verification: AWS Reference deployment

Issue: #30. Checks ADR 0003 left for implementation time. Recorded 2026-10-18.

## FastMCP stateless flags against the adapter

**Verified locally, in the container.** `build_http_app` passes `stateless_http=True` and
`json_response=True`. Against the running image: a request without a key answers 401, an
authenticated `GET /mcp` answers 405, and responses carry no `Mcp-Session-Id`
(`tests/integration/mcp/test_server.py`). Because every reply is a single buffered JSON body,
`AWS_LWA_INVOKE_MODE=buffered` (the adapter default, set explicitly in `deploy/aws/Dockerfile`)
needs no streaming. The adapter image builds and the server starts under it.

## Cold start and source reachability from us-east-1

**Measured live on 2026-10-18** against the deployed function (arm64, 512 MB, Function URL),
through the MCP endpoint. Init and billed durations come from the Lambda `REPORT` lines.

| Check | Result |
|---|---|
| Cold start | Init Duration 5.6 s (first request, billed 5.6 s); warm requests answer in 0.4 to 0.5 s end to end |
| Max memory used | 137 MB of 512 MB |
| No key / `GET /mcp` / `initialize` | 401 / 405 / 200 `application/json`, no `Mcp-Session-Id` |
| `list_coverage`, `tools/list` | 200 |
| `search_legislation` reaches the Senado | 200 in 0.2 to 0.6 s |
| `get_legislation` with `include_text` reaches the Planalto | 200 in 5.6 s (three 404 probes for the consolidated name, then 200 in 2.3 s) |
| `search_cases` reaches DataJud (`tjsp`, limit 1) | reachable but slow: first call timed out at the 20 s limit (`source_unavailable`), the next answered in 18.4 s |
| DataJud from a Brazilian connection (same query) | 200 in 6.6 s and 9.7 s |

Conclusions: none of the three Sources is blocked from `us-east-1`, so `sa-east-1` is not
needed. DataJud is slow from everywhere (about 7 to 10 s from Brazil, about 18 s or more from
`us-east-1`), and its default 20 s timeout is too tight from `us-east-1`; raising
`JURIS_BRIDGE_DATAJUD_TIMEOUT_SECONDS` (through `extra_environment`) is the follow-up. The
5.6 s cold start is dominated by importing FastMCP and building the app; it only applies to
the first request after an idle period.
