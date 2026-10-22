# DJEN `/api/v1/comunicacao/tribunal`

Read-only probe of `https://comunicaapi.pje.jus.br/api/v1/comunicacao/tribunal` on 2026-10-20,
to see whether it can fill `available_from` in `list_coverage` (#73).

## What it returns

A list of 28 groups (`uf`, `nomeEstado`, `instituicoes`) holding 93 institutions, each with
`sigla`, `nome` and `dataUltimoEnvio` (`DD/MM/YYYY`, the last day the institution sent), and
`active` on a few.

## Findings

- **No start date.** It gives the last send, not the first, so it cannot replace the
  `DJEN_START_DATES` seen in sampled weeks (`domain/publication_courts.py`).
- **Every Court the catalog lists as a DJEN sender is in it**, all with a last send in the last 30
  days. The extra entries are `CJF`, `CNJ`, `PJeCor` and `SEEU`, which are not Courts here.
- **STF is not in it**, which matches the findings of #57.
- **The TREs are in it**, 25 of 27 as institutions with a last send between 2024-12 and 2026-10
  (`tre-sp` 2026-10-09, `tre-sc` 2024-12-16), plus the TSE. #57 sampled one week and found 24 of
  27 TREs with no items, so they send, but rarely. ADR 0006 and the issue decided the TREs as
  `not_covered`; this note records that the decision rests on sparse data, not on their absence.
- The spec and reality may drift, as the issue warns; the list is not used at runtime.
