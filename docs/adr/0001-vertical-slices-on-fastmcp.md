# Vertical slices with layers inside, composed through FastMCP

> Superseded by [ADR 0005](0005-layers-at-the-top.md).

The server is split into one self-contained module per concept
(`modules/<concept>`). Each module has five sibling folders: `domain`, `ports`,
`application/use_cases`, `adapters` (port implementations and the MCP inbound
adapter, a FastMCP sub-server) and `infrastructure` (the `container.py` that wires
the module). `bootstrap.py` is the composition root: it mounts each module's
sub-server on the root server with `mount`.

Adding a concept touches one folder and one line in `bootstrap.py`. Use cases
depend on ports (`Protocol`s) in `ports/`, so new data sources are added as
adapters, and use cases are tested with fakes instead of the network.
External services live in `providers/`, shared by modules; modules do not import
each other.

## Considered

- **Horizontal layers at the top** (`mcp/`, `bootstrap/`, `modules/` for the core
  only): a new concept spread across five folders. Replaced.
- **Flat feature folders** (`tools`, `service`, `repository` per feature): fine
  while there is a single provider; revisit if the ports never gain a second
  adapter.

## Conventions

Layer folders may group related files in subdirectories named after a
sub-concept, once about three files share it. The dependency rule applies to the
layer, not to the subdirectory.

Each file has one responsibility (a use case, a settings class, a provider
client). Configuration is separated per concern in `config/` and passed down as
arguments; only `main.py` and `config/` touch the environment. Tools are mounted
without a namespace (verified on FastMCP 4.1.0: `namespace` would rename them to
`cases_search_cases`), so tool names must stay unique across modules.
