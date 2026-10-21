# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Entries are added
under `Unreleased` in the PR that makes the change, and moved under a dated
heading when `development` is released to `master`.

## [Unreleased]

### Added

- Issuing body catalog (#77): a capped DJEN day is split by every known `orgaoId` of the Court,
  from `issuing_bodies.json` shipped with the server, plus any body seen on page 1 that the
  catalog lacks; `slice_cap` is reported only when a slice itself reaches the cap or such a body
  appears. `scripts/build_issuing_body_catalog.py` builds the catalog by hand (ADR 0007). The
  Cursor now carries the catalog position and version (**Break:** earlier publication cursors
  are `invalid_argument`; one from another catalog version asks to restart). The shipped catalog
  covers 32 of the 64 DJEN Courts (the state courts are still missing, see #84); a Court with no
  entry behaves as before.
- List the DJEN Coverage (#73): `list_coverage` adds the `djen` Source (Publications) with the
  Courts that publish there, the `available_from` date known for each and the Courts that are
  `not_covered` (STF and the TREs) with a `reason`. It reads the same module as
  `search_publications` and `get_publication`, so the two cannot disagree. README coverage table. `available_from` and `reason` are left out when unknown, and STF
  and the TREs each get their own reason.
- Read a Publication in full (#72): `get_publication(id, cursor)` returns the whole text of one
  Publication as plain text (HTML stripped) with Content kind `full_text`, in slices of at most
  10,000 characters cut at a space and chained by a stateless Cursor, with `text_length` and the
  Citation. The DJEN has no read-by-id endpoint, so the Court, day and CNJ number in the `id` are
  searched again and the item picked by its hash (`not_found` if gone); a malformed `id` or
  Cursor is `invalid_argument`. A lookup the DJEN truncated or left unread is
  `source_unavailable`, not `not_found`.
- Search Publications by CNJ number (#71): `search_publications` takes `cnj_number` (masked or
  20 digits, check digit validated) to list the Publications of one Case in the window. The
  Court is derived from the number or checked against `court`; `query` becomes optional and,
  when given, filters locally without the 5-character minimum. The number is sent to the DJEN as
  `numeroProcesso`, with the same window, Cursor and `complete` semantics. `court` and `query`
  are required only without a number. No Case enrichment: items carry the CNJ number in both
  forms and the agent calls `get_case`. The tool's `court` and `query` are no longer required
  by the schema, and `date_from`, `date_to` now come first.
  A Case is asked for over the whole window in one DJEN request instead of day by day (checked
  live: the DJEN filters `numeroProcesso` over a range, and a 31-day walk had hit its HTTP 500s).
- Publication ranking (#70): every item of `search_publications` carries `score`, a page-relative
  BM25 computed in pure Python over the texts fetched in the call (accents and case folded, the
  start of the text and the ementa weighted higher) and scaled so the page's best item is 1.0,
  and `matched_terms`. The weights were checked against live DJEN pages. Results stay ordered by
  date; the score is not comparable across pages and there is no global relevance ordering.

### Changed

- Publication query (#69): `search_publications` interprets `query` itself: a space is AND,
  `"exact phrase"`, `OR` groups (at most 3) and `-term` exclusions (at most 8), because the DJEN
  reads `texto` as one ordered phrase. Per group the DJEN gets the longest phrase, otherwise the
  longest word (at least 5 characters); the other words and the exclusions filter the text
  locally, ignoring case and accents and matching by word prefix, and the groups' results are
  united by `id`. Malformed input is `invalid_argument`. The Cursor now carries the OR group
  (**Break:** cursors issued before this change are `invalid_argument`).
- Publication fan-out (#68): `search_publications` walks the window one day at a time, newest
  first, making at most 10 DJEN requests per call. A day at the Source's 10,000 count cap is split
  by `orgaoId` (taken from the ids on its first page). The result says `complete` and, when not,
  `incomplete_reason` (`budget`, `slice_cap`, `depth_ceiling`); the depth-ceiling HTTP 500 is
  truncation, not an error. The Cursor stays opaque and stateless (day, `orgaoId` slice, page).
  A 429 is waited out for 60 s once before `rate_limited`, and the repeat counts against the
  budget. `total` and `total_is_lower_bound`
  are removed: a count over the walked days is not the Source's.
- Errors (#66): `not_covered()` factory in `domain/errors.py`, shared by the DataJud and DJEN
  Court checks.
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

- `search_publications` (#66): searches the Publications of one Court in a window of up to 31
  days over the keyless DJEN API, with the query sent as it is (at least 5 characters, since the
  DJEN answers a shorter one with a misleading HTTP 500). Returns a Normalized result per item
  (opaque `id`, CNJ number in both forms, raw `tipoDocumento`, release date, HTML-stripped
  excerpt, `text_length`, Citation). DJEN failures map to the closed Error codes (429 waits 60 s);
  STF, TREs and periods before a Court's start are `not_covered`. New `JURIS_BRIDGE_DJEN_*`
  settings. No `get_publication` yet (#53).
- Publication `kind` (#67): each item of `search_publications` is classified as `acordao`,
  `sentenca`, `decisao_monocratica`, `decisao_interlocutoria` or `ambiguous` from
  `tipoComunicacao`, `tipoDocumento` and the text (a pure heuristic in
  `domain/publication_kind.py`, stated as such in the response). Despachos, intimações, editais
  and notices are dropped and counted in `not_decisions_dropped`; the new `kind` argument keeps
  one kind. The repository now always asks the DJEN for 100 items, so the limit applies after
  the drop; `total` is still the Source's count before it. A phrase a notice uses ("fica
  intimado", "certidão de") no longer drops a text that rules. STJ and TRF texts open with a party header, so the act's
  name after it (`DESPACHO`, `DECISÃO`) and the Relator's signature at the end now count; checked
  by hand against live DJEN items.
- Publication paging (#67): `search_publications` takes a `cursor` and returns `next_cursor`.
  The Cursor holds the Source page and how many kept items of it were returned, so the `kind`
  filter pages over what it keeps; a call reads at most 3 pages of the DJEN to fill `limit`, and
  stops at the DJEN's 10,000-match ceiling with a hint. A cursor from another Court, window, query
  or kind is `invalid_argument`. Assumes the DJEN keeps its order between calls, which is
  undocumented.
- Publication term in `GLOSSARY.md` and ADR 0006 (#59): the DJEN as the Source of Publications,
  self-hosted per user, extending ADR 0002.
- Diagrams (#32): four overview diagrams under `docs/diagrams/` (architecture and module
  layout, MCP request flow with the wide event, `get_legislation` text fallback chain, AWS
  Reference deployment), each as an HTML source in `code/` and a rendered SVG in `assets/`, with
  the official AWS Architecture Icons for the deployment one. A release PR to `master` must
  regenerate any diagram whose module, flow or ADR changed.
- README (#32): a tool overview, a quick start that ends with a working MCP client configuration,
  the diagrams embedded (architecture, request flow, `get_legislation` fallback; the AWS one in
  `deploy/aws/README.md`), the Apache-2.0 licence and a responsible-use summary.
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
