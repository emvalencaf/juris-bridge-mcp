# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Entries are added
under `Unreleased` in the PR that makes the change, and moved under a dated
heading when `development` is released to `master`.

## [Unreleased]

### Added

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
