# Responsible use

Juris Bridge MCP gives AI agents access to Brazilian judicial and legal data.
The code is licensed under [Apache-2.0](LICENSE), but the data it reaches is not
covered by that licence: each Source has its own terms, and some of them limit
what you may do with the data. This page lists the obligations that follow from
the project decisions ([ADR 0002](docs/adr/0002-self-hosted-datajud-no-browser-sources.md),
[ADR 0004](docs/adr/0004-wide-event-logging-to-stdout.md)) and from the research
notes. It is a statement of how this project is designed to be used, not legal
advice. If your use is anything other than personal or internal, read the
original terms and ask a lawyer.

## Summary

- Run your own instance, with your own DataJud key, for your own non-commercial
  use.
- Do not redistribute DataJud data or anything derived from it.
- Do not run a shared or public instance with DataJud enabled without written
  authorization from the CNJ.
- Do not use the server to profile individuals. It has no party, judge or CPF
  search, and you must not work around that.
- Do not log case numbers, search text or payloads.
- The BNP (Precedents) has no documented API and no terms for programmatic use:
  keep your volume low and run your own instance.

## DataJud: non-commercial use

DataJud is the CNJ public API that provides Case metadata. According to the
research note [DataJud API](docs/research/datajud-api.md#terms-of-use), which
summarises the Terms of Use v1.2 (27 Nov 2023):

- Using the API is tacit acceptance of the terms (1.1, 1.2).
- Use must be lawful, non-commercial and authorized (3.3).
- You must not modify, distribute, sell or commercially exploit the API "or any
  information derived from it" (3.8).
- You must tell the CNJ about any public information, study, report or document
  you produce with it (3.9).
- You must not exceed 120 requests per minute unless the CNJ authorizes it in
  writing (3.13), and the CNJ may impose per-user or per-key limits at any time
  (3.14).
- The CNJ does not guarantee accuracy, completeness or currency (3.6) and may
  change or stop the API, or revoke access, without notice (3.4, 3.22).

The server's rate limiter keeps a single instance under the 120 requests per
minute figure, but the limit is per instance, see [Known limits](docs/known-limits.md).
You remain responsible for your own total volume.

Clause numbers come from the research note, which read the wiki summary of the
terms and the PDF only in part. Check the
[official terms](https://datajud-wiki.cnj.jus.br/api-publica/termo-uso) before
relying on a specific clause.

## No redistribution

Because of clause 3.8, the results of `search_cases` and `get_case` are for your
own use. Do not publish them, resell them, feed them to a service open to
others, or build a dataset from them. The in-memory cache is short-lived and
never persisted, which the research note names as the way to keep caching
compatible with these terms. Do not add a persistent store of DataJud results.

## Self-hosting and shared instances

[ADR 0002](docs/adr/0002-self-hosted-datajud-no-browser-sources.md) records the
consequence of the terms above:

- Each user self-hosts the container with their own DataJud key and answers for
  their own use.
- A maintainer instance, if there is one, is personal and non-commercial.
- **A shared instance needs written CNJ authorization.** That covers an instance
  open to other people or to a team beyond the key holder's own use.
- The project does not offer a public hosted instance. The ADR says to revisit
  that only with written CNJ authorization or a replacement source that allows
  commercial use.
- The AWS Reference deployment is a reference for your own account, and the
  simple API key serves one user or team.

## LGPD and personal data

Judicial data can contain personal data, and the DataJud terms have a section on
the Lei Geral de Proteção de Dados (LGPD, Lei 13.709/2018). According to the
research note, the terms say that you must not:

- use the API to collect third-party personal information (3.11);
- collect, store or process personal data from the API, or cross-reference data
  to that end, except as the LGPD allows (4.2);
- share personal data collected through the API with third parties (4.6).

The project follows from this:

- For Cases the server returns DataJud metadata only. DataJud public data has
  no party or judge fields, and the server adds none. Publications from the
  DJEN do carry party names, which are personal data under the LGPD: use them
  only for the lawful purpose they were searched for and do not collect or
  share them in bulk.
- There are no party-name, judge-name or CPF filters (spec
  [#19](https://github.com/emvalencaf/juris-bridge-mcp/issues/19)), so the
  server cannot be used to profile individuals. Do not extend or wrap it to do
  so.
- The terms describe the API as covering public cases (2.1). The secrecy level
  of a Case is returned as given, and the research did not test whether
  non-zero levels appear in results. Treat any Case you receive as potentially
  sensitive.
- You are the data controller of what you do with the results. The LGPD
  obligations that apply to your use are yours.

## BNP: an undocumented public service

Precedents come from the Banco Nacional de Precedentes (BNP) of the CNJ, which
CNJ Res. 444/2022 makes public for citizens, lawyers, magistrates and
researchers ([ADR 0008](docs/adr/0008-bnp-as-the-source-of-precedents.md), research note
[BNP](docs/research/bnp-precedentes-access.md)). It publishes no API and no terms
for programmatic use: the server reads the JSON backend that the BNP web app
itself calls, without a key. Silence is not a grant, so:

- Run your own instance and keep your volume low. The server limits itself to
  60 requests per minute by default and identifies itself with an honest
  User-Agent; do not raise it to bulk-download the BNP.
- Do not run a public instance for others. A shared one needs written CNJ
  confirmation, as for the DJEN.
- The backend can change or stop without notice; an answer in an unknown shape
  is reported as `source_changed`, not guessed.
- A Precedent is law-level text, but its leading-Case links point to court
  documents that may contain party names. Treat those as personal data under the
  LGPD, as for Publications.
- The BNP holds only what courts send it, so an empty result is not proof that no
  Precedent exists.

## Logging

[ADR 0004](docs/adr/0004-wide-event-logging-to-stdout.md) sets one JSON wide
event per request on stdout. In line with this page, the following are never
logged:

- search text;
- CNJ case numbers, not even hashed, because they are enumerable;
- party names;
- `include_raw` content, response payloads and upstream error bodies.

Only the shape of a call is logged: the filter names present, `limit`, whether a
cursor was sent, the derived court alias, and the norm type and year. A
legislation URN is public and may be logged. The caller is identified by
`caller.key_id`, the first 8 hex characters of the SHA-256 of the API key, never
the key. If you forward these logs elsewhere, keep to the same rule.

## Other Sources

- **Senado, Planalto and Câmara Legin** (legislation): public norm text and
  metadata. The research notes did not confirm a data licence or rate-limit
  policy for the Senado API ([LexML access](docs/research/lexml-access.md)), so
  keep your request volume low.
- **Planalto User-Agent:** the server sends an honest, Mozilla-compatible
  User-Agent that names the project. It does not spoof a browser to get past a
  block; when a Source refuses the call, the result is `source_blocked` or a
  fallback ([ADR 0002](docs/adr/0002-self-hosted-datajud-no-browser-sources.md)).
- **LexML portal:** guarded by a proof-of-work challenge that the server does
  not solve.

## README summary

> **Responsible use.** The code is Apache-2.0, but the data is not. DataJud's
> terms allow only lawful, non-commercial use and forbid redistributing
> information derived from it, so run your own instance with your own DataJud
> key and keep the results for your own use. A shared instance needs written
> CNJ authorization. For Cases the server returns DataJud metadata only, has
> no party, judge or CPF search, and never logs search text, CNJ numbers or payloads. Read
> [RESPONSIBLE_USE.md](RESPONSIBLE_USE.md) before you deploy it.
