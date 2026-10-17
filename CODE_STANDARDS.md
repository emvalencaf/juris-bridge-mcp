# Code Standards

These standards apply to everything committed here. Tool settings live in
`pyproject.toml`, which is the source of truth; this file names the tools instead
of repeating their values.

## General

- Keep changes small and focused; one concern per commit.
- No secrets, tokens or personal data in the repo. Use `.env` (ignored) and
  document variables in `.env.example`.
- Every behavior change comes with a test, or a stated reason why not.

## Stack

- Language: Python ≥ 3.12, managed with `uv`.
- Lint and format: `ruff` (config in `pyproject.toml`, including the `S` security rules), enforced by the `pre-commit` hook and CI.
- Types: `mypy` (config in `pyproject.toml`), run in CI.
- Encoding: UTF-8, NFC-normalized, no BOM, no zero-width or bidi control characters
  (enforced by `scripts/check_unicode.py`).
- Test command: `uv run pytest` (`pytest` with `pytest-asyncio`); tests live in `tests/`.
- Directory layout: flat package `juris_bridge_mcp/` at the repo root; tests in `tests/`.
  See [Architecture](#architecture).
- Docstrings: Google style on public modules, classes and functions.

## Architecture

Modular and layered, one concept per module, following FastMCP's server model
([ADR 0001](docs/adr/0001-vertical-slices-on-fastmcp.md)).

| Path (under `juris_bridge_mcp/`) | Role |
|---|---|
| `main.py` | Entry point: reads settings, starts the server |
| `bootstrap.py` | Composition root: builds shared clients, mounts one FastMCP sub-server per module on the root server |
| `config/` | One settings class per concern (`server.py`, `http.py`, `datajud.py`), each with its own `JURIS_BRIDGE_<CONCERN>_` env prefix; shared base in `base.py` |
| `health.py` | Plain HTTP routes outside MCP |
| `modules/<concept>/` | A self-contained vertical slice, one per concept (see below) |
| `providers/<name>/` | External service: `client.py` (transport), `queries.py`, `schemas.py`, `errors.py`; shared by modules, knows nothing of any domain |
| `shared/` | Cross-cutting errors, HTTP client factory, observability |

Inside `modules/<concept>/`, five sibling folders (flat, none nested in another):

| Folder | Holds |
|---|---|
| `domain/` | Entities, value objects and domain errors; pure, imports only `shared/` |
| `ports/` | The interfaces (`Protocol`s) the module needs or offers; one per file |
| `application/use_cases/` | One use case per file; depends on `ports/` and `domain/` only |
| `adapters/` | Implementations of ports (e.g. `datajud_case_repository.py`) and the module's inbound adapter (`mcp_tools.py`, a FastMCP sub-server) |
| `infrastructure/` | Technical wiring of the module (`container.py`: builds adapters, injects them into use cases, returns the sub-server) |

Any of these folders may contain subdirectories that group related files by
sub-concept, e.g. `application/use_cases/movements/`, `adapters/datajud/` or
`ports/repositories/`. Rules: create one when about three or more files share a
sub-concept (not before), name it after the sub-concept (never `misc` or `utils`),
and keep it to one level unless a second one clearly pays off. Subdirectories do
not change the dependency rule below, and imports stay absolute from the package
root.

Adding a concept means adding a `modules/<concept>/` folder and one `app.mount(...)`
line in `bootstrap.py`. Rules: one concept per module, one responsibility per file,
modules do not import each other (share through `shared/` or a port). Settings are
never read outside `config/` and `main.py`; they reach other code as arguments.

Dependency rule (arrows are "may import"):
`adapters` → `application` → `ports` → `domain`; `infrastructure` → everything in
its module. `domain` imports no other layer; `ports` and `application` never import
`adapters`, `infrastructure` or `providers`. Tests mirror it:
`tests/unit/modules/`, `tests/contract/providers/`, `tests/integration/mcp/`.

## Documentation

- Every project `README.md` follows the section structure of
  [Best-README-Template](https://github.com/othneildrew/Best-README-Template), in
  this order: header block (title, one-line description, links), Table of Contents,
  About The Project (with Built With), Getting Started (Prerequisites,
  Installation), Usage, Roadmap, Contributing, License, Contact, Acknowledgments.
  Drop a section that does not apply instead of leaving it empty.
- Keep the `readme-top` anchor and a "back to top" link after each section.
- Start a new README from
  `.agents/skills/setup-project-harness/assets/README.template.md`; `/setup-project-harness`
  does this for you.
- Do not add badges that point to a private repository (they render broken), and
  do not put personal e-mail addresses in the README; link the GitHub profile.
- Update the README in the same PR as the change it describes.

## Skills

- **Location:** the source lives in `.agents/skills/<name>/`. `.claude/skills/<name>`
  is a relative symlink to it (`../../.agents/skills/<name>`). Never duplicate a
  skill's files.
- **Entry point:** each skill has a `SKILL.md` with YAML frontmatter:
  - `name` — matches the directory name, kebab-case.
  - `description` — what it does **and** when to use it, including trigger
    phrases. This is what an agent reads to decide whether to invoke it.
  - `user-invocable` and, when it takes input, `argument-hint` listing every
    argument (`<required>`, `[optional]`).
  - `allowed-tools` — the minimum needed; read-only skills get no write tools.
- **Body:** imperative instructions for an agent, not prose for a human. State
  defaults, limits and failure behavior explicitly. Keep `SKILL.md` short; move
  long material to `references/` and link it.
- **Supporting files:** never leave them loose in the skill root, which holds
  only `SKILL.md` and these folders: scripts in `scripts/`, documents the agent
  reads on demand in `references/`, and templates or seed files the agent copies
  into a project in `assets/`. Link them from `SKILL.md` with relative paths.
  Scripts must be deterministic and runnable from the CLI.
- **Third-party skills** tracked in `skills-lock.json` follow the same layout.
  Moving their files changes the lock hash and a `skills update` brings the files
  back to the root, so re-apply the layout after updating. Local skills are not
  listed there.

## Markdown

- One H1 per file. Headings in sentence case.
- Wrap prose at ~80 columns. Tables and code blocks are exempt.
- Fenced code blocks always declare a language (`bash`, `yaml`, `text`).
- Use relative links between files in the repo.

## Scripts

- Python scripts run with `uv run` and declare dependencies inline (PEP 723).
- Fail with a non-zero exit code and a clear message; never swallow errors.

## Language

- Code, comments, commits, PRs and documentation are written in English.

## Review checklist

- [ ] Follows the commit convention in [CONTRIBUTING.md](CONTRIBUTING.md)
- [ ] Skill frontmatter complete; `.claude/skills` symlink present
- [ ] No secrets, tokens or personal data
- [ ] [CHANGELOG.md](CHANGELOG.md) updated
