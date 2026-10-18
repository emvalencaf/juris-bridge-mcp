# Layers at the top of the package, superseding vertical slices

ADR 0001 split the code into `modules/<concept>/`, each with its own `domain`,
`ports`, `application`, `adapters` and `infrastructure`. With the MVP's two
concepts (Cases and Legislation) and a first module that is a single read-only
tool, that level of nesting costs more than it separates: five folders wrapped
around a few files, and cross-cutting code (Error codes, Bearer auth, the
composition root) with no natural home, which pushed it into a `shared/` bucket.

The layers now sit directly under `juris_bridge_mcp/`: `domain/`, `ports/`,
`application/use_cases/`, `adapters/` and `infrastructure/`, plus `config/` and
`main.py`. The dependency rule is unchanged. Error codes live in `domain/`, the
Bearer middleware is an inbound adapter, and `infrastructure/bootstrap.py` is the
composition root that mounts one FastMCP sub-server per concept. External
services are adapters, grouped in a sub-concept folder (`adapters/datajud/`) once
about three files share it; there is no top-level `providers/` or `shared/`.

## Considered

- **Keep `modules/<concept>/` (ADR 0001):** isolates a concept in one folder and
  enforces "concepts do not import each other" by structure. Dropped because it is
  ceremony at this size.
- **Keep `shared/` for errors and auth:** a catch-all name that hides which layer
  the code belongs to.

## Consequences

Isolation between concepts is now a convention (sub-concept folders, no
cross-concept imports, share through `domain/` or a port) and not enforced by the
folder structure. Revisit if the number of concepts grows enough that a single
layer folder becomes hard to navigate.
