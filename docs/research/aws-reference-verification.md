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

**Not yet measured.** No AWS credentials were available when this was implemented, so these
two checks are open. To close them, run `deploy/aws/wizard.sh` (its smoke test prints the first
`initialize` time; the `cold-starts` Logs Insights query shows `duration_ms` for
`cold_start = 1`) and call each Source once through the deployed server:

| Check | Result |
|---|---|
| Cold start, `initialize` (arm64, 512 MB) | _to record_ |
| `search_cases` reaches DataJud from us-east-1 | _to record_ |
| `search_legislation` reaches the Senado from us-east-1 | _to record_ |
| `get_legislation` with `include_text` reaches the Planalto from us-east-1 | _to record_ |
| The same three Sources from `sa-east-1` (only if any us-east-1 check fails) | _to record_ |

If a Source answers 403 or times out from `us-east-1`, set `region = "sa-east-1"` and re-check;
record the outcome here.
