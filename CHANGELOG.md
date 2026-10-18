# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Entries are added
under `Unreleased` in the PR that makes the change, and moved under a dated
heading when `development` is released to `master`.

## [Unreleased]

### Added

- Norm text from the Planalto (#28): `get_legislation` takes `include_text` (plain text sliced
  by `max_chars`, default 20,000, with `truncated` and `next_text_cursor`; `content_kind:
  full_text`) and `article` (one article such as `Art. 5º`, `121-A` or `Art. único`, with
  `flags` `revoked` and `superseded` when the page marks them). An article the parser cannot
  locate returns `not_found`; a Planalto refusal returns `source_blocked` and a page the
  parser no longer reads returns `source_changed`. A norm with no locatable page returns
  metadata and a warning. Adds `JURIS_BRIDGE_PLANALTO_*`.
- `get_legislation` tool (#27): fetch a federal norm by URN Lex from the Senado `legislacao/urn`
  service: type, number, year, signature date, name, nickname, ementa, Citation,
  `publications` (Diário Oficial `edition`, page, column) and `relations`. Relations are
  collapsed per related norm and kind, sorted newest first and cut to `relations_limit` (default 25, max 100) with `relations_total`.
  Content is `metadata` unless the text is asked for.
  An unknown URN returns `not_found`; `include_raw` works as in `get_case`.
- `search_legislation` tool (#26): locate a federal norm by `type` (`lei`,
  `lei-complementar`, `decreto`, `decreto-lei`, `medida-provisoria`,
  `emenda-constitucional`), `number` and `year` through the Senado open-data API; no
  free-text search. Results carry the URN Lex, a Citation with the `normas.leg.br` URL,
  `source`, `retrieved_at` and `content_kind: metadata`. `limit` and the Cursor behave as
  for cases, with an offset in the same Cursor format. Adds `JURIS_BRIDGE_SENADO_*`.
- `search_cases` tool (#25): search a Court's Cases by `case_class`, `judging_body`,
  `subject` and `filed_from`/`filed_to` (no party, judge or CPF filters). `court` is
  checked against the embedded allowlist; `limit` is 1-50 (default 10). Paging uses a
  stateless opaque Cursor that carries the Court alias, over a `[@timestamp,
  id.keyword]` sort so no item is skipped or repeated. The envelope has `total`,
  `total_is_lower_bound` and a narrowing `hint` at DataJud's 10,000-hit cap.
- `get_case` tool (#24): fetch one Case by CNJ number from DataJud. Accepts the formatted
  or 20-digit number and validates the check digit; derives the Court from `J.TR`
  (override with `court`); returns events honouring `events_limit`, a Citation with a
  `null` URL and, on request, the raw payload. STF returns `not_covered`. Adds
  `JURIS_BRIDGE_DATAJUD_CACHE_TTL_SECONDS`.
- Wide-event logging (ADR 0004): `WideEventMiddleware` emits exactly one JSON line per
  HTTP request on stdout, with environment, request, caller (`key_id`) and upstream
  context and a never-logged list; configured by `JURIS_BRIDGE_LOG_*`. Events flag
  `upstream_truncated` and `mcp.body_oversized` when they had to cut.
- Architecture convention: layers at the top of the package (`domain`, `ports`,
  `application/use_cases`, `adapters`, `infrastructure`) with concepts mounted as
  FastMCP sub-servers (see `CODE_STANDARDS.md` and ADR 0005), plus `.env.example`,
  a `Dockerfile` and the `tests/` layout.
- `GLOSSARY.md` with the initial domain language.
- Research notes under `docs/research/`: DataJud API, LexML access, court data
  access, AWS deployment options, legislation access (Playwright and
  alternatives) and a benchmark of similar legal-data MCP servers.
- ADR 0002: DataJud is self-hosted per user and the MVP sources (DataJud, Senado
  API, Planalto/Câmara Legin) need no browser; `URN Lex` added to `GLOSSARY.md`.
- ADR 0003: stateless Lambda with the Web Adapter as the AWS reference deployment,
  with the container plus environment variables as the portability boundary.
- ADR 0004: one wide event per request as JSON on stdout for observability.
- `GLOSSARY.md`: Citation, Content kind, Cursor, Coverage and Error code, and
  the MVP source set (Senado API) in the Source and Legislation entries.
- Server skeleton: stateless FastMCP over streamable HTTP with JSON responses
  (GET answers 405, no `Mcp-Session-Id`), Bearer API-key auth (several
  comma-separated keys, constant-time compare, 401 otherwise) and a refusal to
  start without a key, plus a one-line responsible-use notice at startup.
- `list_coverage` read-only tool stating the supported Sources and Courts, with
  a per-court `citation_url` flag (all `false`) and no network call.
- Shared closed set of 8 Error codes and the MCP error shape.
- Per-concern settings classes (`server`, `http`, `datajud`) documented in
  `.env.example`, and in-memory MCP and ASGI test harnesses.
- ADR 0005: layers at the top of the package instead of one module per concept,
  superseding ADR 0001.
- Shared upstream HTTP client (honest Mozilla-compatible User-Agent, configurable
  timeout, DataJud default 20 s), per-instance rate limiter (`rate_limited` with
  `retry_after_seconds` instead of blocking past about 5 s), 2 jittered retries
  on 429/503, and a `Cache` port with an in-memory TTL implementation. Known
  limits: the rate limit is per instance, not global, and the cache lives per
  warm environment. The client keeps its total waiting (limiter plus backoff)
  within the wait budget, and the cache is capped at 1024 entries.
