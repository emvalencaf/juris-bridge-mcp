# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Entries are added
under `Unreleased` in the PR that makes the change, and moved under a dated
heading when `development` is released to `master`.

## [Unreleased]

### Changed

- Planalto norm text (#43): the rubric title of the next article (e.g. `Lugar do crime`) no
  longer trails the previous article, and a heading without accents (`TITULO`), a `SUBTÍTULO` or a
  line in capitals (`DAS PENALIDADES`) now ends the article before it. Known limits of the flags,
  article boundaries and page paths are documented in the README and the `get_legislation`
  description.
- Cursor (#40): `Cursor.court` is now the neutral `scope`, and the position is whatever the
  search needs, validated by the use case that issued it (a sort position for Cases, an offset
  for Legislation). `Cursor.decode` now requires the `scopes` it accepts.
  **Break:** legislation search and norm-text cursors issued before this change (position
  `[offset, 0]`) are rejected as `invalid_argument`; repeat the call without a cursor. Case
  cursors keep their format, and one with a malformed position is now also rejected.

### Added

- Licence and responsible use (#32): the Apache-2.0 `LICENSE`, `RESPONSIBLE_USE.md` (LGPD,
  DataJud non-commercial terms, no redistribution, a shared instance needs written CNJ
  authorization, no profiling, nothing sensitive logged, with a README-ready summary) and
  `docs/known-limits.md` explaining the per-instance rate limit and the per-warm-environment
  cache on Lambda.
- Câmara Legin text fallback (#29): when the Planalto has no page for a norm or refuses, the
  text of `get_legislation` comes from Câmara Legin, then metadata and links only.
  `text_source` is `camara_legin` and `warnings` say that the fallback supplied the text and
  why, give the amending norms and the remark of the Câmara data sheet as hints, and flag
  jumps in the article numbers. The Legin URL is resolved through the LexML URN page and the
  data sheet (`JURIS_BRIDGE_LEGIN_*`); a portal challenge is `source_blocked`, never solved,
  and a gateway error served with status 200 is `source_unavailable`. When the Planalto
  failed and Legin has nothing, the Planalto failure is returned. Range stubs such as
  `Arts. 757 a 777. (Revogados ...)` now open one revoked article per number, in both Sources,
  instead of trailing the article before them. **Break:** `build_server` and `build_http_app`
  take a `legin` settings argument.
- `include_annotations` on `get_legislation` (#49): `false` leaves the Annotations (`Redação
  dada ...`, `Incluído ...`, `Vide ...`, `Vigência`, `Regulamento`, `Renumerado ...`, `Produção
  de efeito`) out of the norm text to save tokens; `(Revogado ...)` is always kept. The default
  `true` changes nothing. `max_chars` and the text cursor count the text after removal, and a
  cursor is tied to the value, so one issued under the other is `invalid_argument`. A warning
  says when notes were omitted. **Break:** norm-text cursors issued before this change are
  rejected as `invalid_argument`; repeat the call without a cursor.
- Container and AWS Reference deployment (#30): a small, Playwright-free image that starts
  without resolving or writing anything (`python` from the venv), and `deploy/aws/` with the
  Lambda Web Adapter image (`buffered`), Terraform (Lambda, Function URL with auth `NONE`,
  30-day log group, saved Logs Insights queries, secrets as sensitive variables) and a guided
  `deploy.sh`. A test guards that the package never imports an AWS SDK.
- Legislation search cache (#39): a Senado search is kept per filters (default 5 minutes, 64
  searches; `JURIS_BRIDGE_SENADO_CACHE_TTL_SECONDS`, `JURIS_BRIDGE_SENADO_CACHE_MAX_ENTRIES`), so
  every page of it costs one upstream request. `retrieved_at` is when the Senado was asked.
- Norm text cache (#42): the parsed Planalto text is kept per URN (default 1 hour, 16 norms;
  `JURIS_BRIDGE_PLANALTO_CACHE_TTL_SECONDS`, `JURIS_BRIDGE_PLANALTO_CACHE_MAX_ENTRIES`), so
  paging a long norm or asking for several articles fetches the page once and skips the
  404 probes for the consolidated name. The cache is per warm environment.
- Norm text from the Planalto (#28): `get_legislation` takes `include_text` (plain text sliced
  by `max_chars`, default 20,000, with `truncated` and `next_text_cursor`; `content_kind:
  full_text`) and `article` (one article such as `Art. 5º`, `121-A` or `Art. único`, with
  `flags` `revoked` and `superseded` when the page marks them). An article the parser cannot
  locate returns `not_found`; a Planalto refusal returns `source_blocked` and a page the
  parser no longer reads returns `source_changed`. A norm with no locatable page returns
  metadata and a warning. For laws, decrees and decree-laws the consolidated Planalto page
  (the law in force) is preferred over the text as first published. Adds
  `JURIS_BRIDGE_PLANALTO_*`. `scripts/try_legislation.py` calls the tool live, guided or by flags.
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
