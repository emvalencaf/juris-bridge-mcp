# DJEN as the Source of Publications, self-hosted per user

Publications (decisions and rulings released in a Diário) come from the DJEN
public read API (`comunicaapi.pje.jus.br`), which replaces each court's DJe
(CNJ Res. 455/2022). The DJEN publishes no terms of its own: the API text allows
keyless reading and warns that abuse is blocked, and says nothing on
redistribution, commercial use or caching. Party names are mandatory in
publications and LGPD still applies. So ADR 0002 extends to this Source: each
user self-hosts, there is no public instance, and a shared one needs written CNJ
confirmation.

The tools are `search_publications` and `get_publication`, plus `list_coverage`
extended to the DJEN. The DJEN has no read-by-id endpoint, no server-side filter
by kind and a depth ceiling, so the server fans out over court, day and
`orgaoId`, classifies kinds on its side (`ambiguous` when unsure), and states
when a result is not exhaustive. Courts the DJEN does not reach (STF, TREs) are
`not_covered`; no portal is scraped and no fallback is attempted (ADR 0002).

## Considered

- **Public hosted instance:** conflicts with the DataJud terms already, and the
  DJEN terms are silent, which is a gap, not a grant.
- **Scraping each court's DJe or case-law portal:** reaches STF and older
  years, but is blocked by challenges (WAF, proof of work) that we do not
  circumvent.
- **Extending `search_cases`:** a Case has a CNJ number and movements; a
  Publication has text and a release date, so the shapes diverge.

## Consequences

History is only as long as each court's DJEN start (about 2021 onward, later for
many courts); recent decisions are the v1 scope. Party names are returned as
published and the tool descriptions warn about personal data; masking is an open
question. The Case link and the integrated search are a later step.
