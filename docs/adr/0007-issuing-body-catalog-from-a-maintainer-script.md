# Issuing body catalog shipped as a static file

A DJEN day that reaches the count cap (10,000) is split by `orgaoId`. Taking the ids
from the first page leaves out every body with no item on it (#68). The DJEN has no
endpoint listing the Issuing bodies of a Court, and scraping court portals is ruled
out (ADR 0002), so the server needs its own list.

## Decision

A catalog of Issuing bodies (`orgaoId` and name) per Court ships with the server as
`juris_bridge_mcp/adapters/djen/issuing_bodies.json`, with a `version` and a
`generated_on` date. A capped day is split by every catalog body of the Court plus
any body seen on its first page that the catalog lacks.

- **Source:** `scripts/build_issuing_body_catalog.py`, run by hand by the maintainer.
  It aggregates `idOrgao`/`nomeOrgao` from recent days, probing capped days with
  common words, paced to the DJEN limit. The output keeps ids and body names only:
  no publication text, no party names.
- **Refresh:** manually, per release or when a search reports an unexpected
  `slice_cap`. The merge is additive and bumps `version` when it changes.
- **Cursor:** stays opaque and stateless. It carries the position in the catalog
  (an index) and the catalog `version`, plus the few bodies page 1 showed that the
  catalog lacks. A Cursor issued under another version is `invalid_argument`, with a
  hint to restart.
- **`slice_cap`** is reported only when a body slice itself reaches the cap, or page 1
  shows a body missing from the catalog. A Court with no entry behaves as before.

## Considered

- **Learning bodies at runtime or caching them:** needs a persisted or shared store;
  out of scope (stateless Lambda, ADR 0003).
- **Scheduled refresh in CI:** more moving parts for a list that changes slowly.
- **Reading the ids from narrower probes on every call:** spends the 10-request budget.

## Consequences

A body that is both missing from the catalog and absent from page 1 cannot be
detected; see [known limits](../known-limits.md). A capped day may now cost several
calls (`budget`), one request per catalog body.
