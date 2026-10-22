# BNP as the Source of Precedents, self-hosted per user

Precedents come from the Banco Nacional de Precedentes (Pangea/BNP, CNJ Res.
444/2022), a public tool open to citizens, through the JSON backend its web app
calls anonymously at `pangeabnp.pdpj.jus.br/api/v1` (see
`docs/research/bnp-precedentes-access.md`). That backend is not documented and
has no terms for programmatic use, and its shape can change without notice. We
treat it as a public service and do not wait for a CNJ authorization; the
decision stands on Res. 444 art. 1 (consultation by the public at large).

The ADR 0006 pattern applies: read-only and keyless, self-hosted per user, no
public instance, an honest User-Agent and conservative throttling. Because the
API is unversioned, the adapter sits behind a `PrecedentSource` port, a contract
cassette is recorded from a live probe and an opt-in drift check reports
`source_changed`. Tools are `search_precedents` and `get_precedent`, plus
`list_coverage` extended to the BNP bodies.

## Considered

- **Waiting for written CNJ confirmation:** safer, but blocks a public service
  whose records are law-level text; revisit if the CNJ objects.
- **STJ CKAN `precedentes-qualificados`:** documented and open, but only STJ;
  kept as the fallback behind the same port.
- **Extending `search_publications`:** a Precedent is a thesis record, a
  Publication is the text of one ruling, so the shapes diverge.

## Consequences

Coverage is whatever courts send to the BNP and is uneven by body; results state
it instead of promising it. `total` is capped at 10,000, the status is free text
and decision texts may be empty, so results carry those limits. If the CNJ
withdraws or changes the backend, only the adapter changes.
