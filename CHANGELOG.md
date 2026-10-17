# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Entries are added
under `Unreleased` in the PR that makes the change, and moved under a dated
heading when `development` is released to `master`.

## [Unreleased]

### Added

- Architecture convention: self-contained modules mounted as FastMCP sub-servers,
  each with `domain`, `ports`, `application/use_cases`, `adapters` and
  `infrastructure` (see `CODE_STANDARDS.md` and ADR 0001), plus `.env.example`,
  a `Dockerfile` and the `tests/` layout.
- `GLOSSARY.md` with the initial domain language.
- Research notes under `docs/research/`: DataJud API, LexML access, court data
  access, AWS deployment options, legislation access (Playwright and
  alternatives) and a benchmark of similar legal-data MCP servers.
