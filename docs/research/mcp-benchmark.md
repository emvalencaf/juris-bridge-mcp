# Benchmark: legal-data MCP servers (issue #10, map #1)

Researched 2026-10-17. Sources: GitHub repos (README, license and push metadata via the GitHub API) and vendor docs. Star counts and push dates are a snapshot of that day. "README claims" means I read the vendor's own text and did not run the server.

## 1. Comparison table

| Project | Tool names / granularity | Result shape | Auth | Deployment | Source coverage | License | Maintenance (snapshot) |
|---|---|---|---|---|---|---|---|
| **CourtListener MCP** (Free Law Project) [1][2] | About 15 tools: `search`, `get_endpoint_item`, `get_more_results`, `get_counts`, generic `call_endpoint` / `get_endpoint_schema` / `get_choices`, `extract_citations`, `analyze_citations` / `resume_citation_analysis`, `get_api_usage`, alert tools. Few verbs plus a generic escape hatch. | Paginated (max 100 per call, default 20), `fields` param to trim columns, `job_id` for resumable batch jobs. `analyze_citations` returns canonical name, court, date, status `good`/`bad`/`ambiguous`. | OAuth 2.1 with RFC 9728 metadata; API token accepted for clients that cannot run OAuth. | Hosted at mcp.courtlistener.com (Streamable HTTP). Self-host via PyPI `courtlistener-api-client[mcp]` (stdio) or docker compose (HTTP + OAuth). `/health` and `/metrics` endpoints. | US case law, RECAP/PACER, oral arguments, judges, citation graph. | BSD-2-Clause (client/server repo) | Active: pushed 2026-10-14, 31 stars. Non-profit operator. |
| **jurismcp** (ivancaron) [3] | One tool per court, all named `<Court>LegalPrecedentsRequest` (STJ, STF, TST, TJES, LexML, Jurisprudencias.ai, BNP, TNU, TRF4). Court-specific operators and filters. | List of precedents with a canonical `summary` (ementa), plus optional `full_text`, `full_text_url`, `court`, `urn`, `relator_original`, `divergencia_vencedora`. Optional fields default to None. | None for official sources. Optional third-party token for Jurisprudencias.ai (env var; free tier 5 searches/day). | Local stdio (`uv run serve`). STF and TST need headless Chrome. | STJ, STF, TST, TJES, TNU, TRF4, BNP (CNJ qualified precedents), LexML. No DataJud. | MIT | Pushed 2026-09-30, 30 commits, 0 stars. Documents LexML anti-bot block from 2026-09-29. |
| **br-eli-mcp** (matematicsolutions) [4] | 15 tools, a `br_<verb>_<noun>` pattern: `br_search_*` / `br_get_*` pairs per source, `br_get_norma_index` + `br_get_norma_texto` for article-level text, `br_coverage`. | Every response carries `lex_uri`, `human_readable_citation`, `source_url`. | Keyless. | Local stdio (pip or Claude plugin). Local cache and audit dirs. One first-run fetch of a runtime config file from GitHub Releases. | Câmara bills, Senado norms (URN Lex), normas.leg.br article text, DataJud (dockets only), STJ open data (from May 2022), CARF, TST, TCU. | Apache-2.0 | Pushed 2026-10-08, 1 star. |
| **mcp-juridico-brasil** (DeHor-Labs; v0.5.0 mirror at ehrodan/lexmcp) [5] | 9 tools plus 1 resource. Process-centric: `buscar_processo_por_numero`, `listar_movimentacoes`, `resumir_andamento`, `monitorar_processo`, `calcular_proximo_prazo` (CPC deadlines, offline), `listar_tribunais`, and DJe tools `listar_intimacoes` / `confirmar_leitura_intimacao`. | Docket data plus an "instruction for the LLM" in `resumir_andamento`. `confirmar_leitura_intimacao` defaults to dry-run. | DataJud public key built in, `DATAJUD_API_KEY` overrides it. DJe needs its own OAuth credentials. | Local stdio via `uvx`. | DataJud only (92 court acronyms; README says registration does not guarantee data). DJe optional. No case-law text. | MIT | Pushed 2026-10-17, 114 stars. |
| **mcp-brasil** (Mcp-Brasil) [6] | 533 tools across 70 features. Judiciary: `datajud` (7 tools), `jurisprudencia` (6 tools: STF, STJ, TST). Adds `planejar_consulta`, `executar_lote` and BM25 tool search to cope with the tool count. | Not inspected. | Mostly keyless; `DATAJUD_API_KEY` for DataJud. | Local stdio; HTTP via `fastmcp run --transport http`. Dockerfile in repo. | 70 public Brazilian APIs; legal is a small part. | MIT for code; data licenses per `SOURCES.md`; `ACCEPTABLE_USE.md` | Most stars (1811). Last commit 2026-08-19 (push 2026-09-19). |
| **Legal MCP / jusbrasil-mcp** (mcp-dir) [7] | 20 tools, flat: `djen_search_comunicacoes`, `jurisprudencia_buscar`, `jurisprudencia_sumulas`, `processos_buscar_por_nome` (async job + `processos_get_resultado` polling), `legal_dossie`, monitor tools. | Not inspected (the repo holds manifests and docs only). | Not required, per README. | Hosted proprietary service at `api.mcp.ai/legal`. Repo holds only manifests and docs. | DJEN, DataJud, LexML jurisprudence, name-based scraping of court portals, sanctions, municipal gazettes. | Repo MIT; server proprietary; "free" | Pushed 2026-08-30, 5 stars. Name and CPF search is a LGPD-sensitive use case (see section 3). |
| **mcp-eu-sparql** (matematicsolutions) [8] | 5 tools: `search_by_celex`, `search_by_date_range`, `search_cjeu`, `search_cjeu_by_ecli`, `search_gdprhub`. Identifier-first. | `structuredContent.citations[]` of `{title, url, celex?, ecli?, publication_date?, document_type?, snippet?, license?}`. Shared citation contract across the vendor's servers. | Keyless. | Local stdio (npx). Offline fixture tests plus live smoke test. | EUR-Lex/Cellar via SPARQL, CJEU case law, GDPRhub. | MIT (GDPRhub content CC BY-NC-SA 4.0, flagged per citation) | Pushed 2026-10-13, 1 star. |
| **gb-eli-mcp** (matematicsolutions) [9] | 9 tools: `gb_search`, `gb_get_act`, `gb_get_text` (xml, html, akn, rdf, pdf, csv), `gb_recent_legislation`, `gb_search_case_law`, `gb_get_case`, `gb_search_govuk`, and others. | `source_url` on every response; stable id URI instead of a fabricated ELI. | Keyless. | Local stdio. | legislation.gov.uk (OGL v3.0), Find Case Law, GOV.UK. | Apache-2.0 | Pushed 2026-10-15, 0 stars. |
| **comprehensive-eu-law-mcp** (Ansvar) [10] | Not inspected. | Not inspected. | Not inspected. | Not inspected. | EU treaties, key acts, CJEU case law. | Apache-2.0 | Repository archived. Pushed 2026-08-03. |

## 2. Findings by dimension

- **Granularity.** There are three patterns.
  - One tool per court (jurismcp). This duplicates the schema per court, pushes court selection onto the model, and needs court-specific operator syntax in each tool description.
  - Search/get pairs per source (br-eli-mcp, eu-sparql, gb-eli-mcp). These stay predictable, and `get` takes exact identifiers (CNJ process number, URN Lex, CELEX/ECLI).
  - A kitchen sink (mcp-brasil, 533 tools). Its authors had to add BM25 tool search and batch tools to stay usable.
  - CourtListener uses a few verbs plus a generic escape hatch, which keeps the tool list small.
- **Result shape.** br-eli-mcp, eu-sparql and gb-eli-mcp put a citation block (`source_url`, a persistent id, a human-readable citation) on every result. This is the closest match to our "normalized + `source` + citation URL + optional `include_raw`" decision. jurismcp has a minimal canonical field (`summary`) plus nullable optional fields. CourtListener adds `fields` filtering and pagination helpers.
- **Auth.** Local servers are keyless or use env keys. The two hosted servers I could read use OAuth (CourtListener) or no auth (api.mcp.ai/legal, per its README). None of the Brazilian servers I read documents a static API key for a remote server, so our "remote streamable HTTP + simple API key" choice has no Brazilian precedent in this sample. CourtListener's token fallback for non-OAuth clients is the closest precedent.
- **Deployment.** Nearly all Brazilian servers are local stdio (`uvx`, `uv run`, pip). Hosted options are CourtListener and the proprietary api.mcp.ai/legal. I found no open-source, container-first remote server for Brazilian sources, which is the gap we target.
- **Source coverage.**
  - DataJud returns dockets and movements, not ruling text. br-eli-mcp says so explicitly and cites CNJ Resolution 446/2022 as restricting redistribution (the resolution text itself is not verified, see section 4).
  - Case-law text comes from per-court scrapers (jurismcp), STJ open data (br-eli-mcp, May 2022 onward), or LexML.
  - LexML has been behind an anti-bot check since 2026-09-29 (per the jurismcp README). This puts one of our two MVP sources at risk.
  - Some courts are unreachable: br-eli-mcp reports TRF4 and TRF5 hosts are geo-restricted from outside Brazil. This matters for a `sa-east-1` deployment only if the problem is egress location. It was not verified for our case.
- **Licensing.** The code is permissively licensed across the sample, mostly MIT or Apache-2.0. Data terms are handled separately: mcp-brasil ships `SOURCES.md` and `ACCEPTABLE_USE.md`, eu-sparql flags the non-commercial GDPRhub license per citation, and jurismcp's foreword warns about overloading official servers.
- **Maintenance.** Most projects were pushed within the last 30 to 60 days, but star counts are low (0 to 114) except mcp-brasil (1811). Several are single-maintainer projects, and several carry "Part of a fleet" branding. The one archived repo (Ansvar) shows that churn is real.

## 3. Lessons for our tool contract and positioning

1. **Tool granularity.** Prefer a small set of `search_*` / `get_*` tools keyed to source-agnostic nouns (for example `search_case_law`, `get_case`, `search_legislation`, `get_legislation`, `get_process`), with `source` and `court` as arguments, over one tool per court. This follows jurismcp's lesson in reverse: its per-court tools force the model to pick the right schema. Tool names must stay unique across modules (ADR 0001). A `coverage` tool (br-eli-mcp's `br_coverage`) that states what is and is not covered, with fallbacks, fits the Brazil-specific uncertainty well.
2. **Identifier-first `get`.** Accept exact identifiers: CNJ unified process number, URN Lex, and later CELEX/ECLI-style ids for other jurisdictions. Return the identifier back on every result so the agent can chain calls.
3. **Result envelope.** Always return `source`, a persistent id (for example `urn:lex`), `human_readable_citation` and `source_url`. Keep optional fields nullable and additive (jurismcp's backward-compatible pattern). Offer `include_raw` as already decided. Add `fields` filtering and pagination (`limit`, cursor) like CourtListener, with a hard cap per call.
4. **Be honest about what each source is.** Docket metadata (DataJud) and ruling text (courts, LexML) are different things. Mark them in the result (for example a `content_kind` field or separate tools) so agents do not read an empty list as "no case law". jurismcp returns an explicit error when LexML serves its anti-bot page rather than an empty result. We should do the same: errors must be explicit and distinguishable from "no results".
5. **Error model.** Distinguish source-blocked, source-unavailable, invalid-argument and not-found. Model the error contract on jurismcp's explicit `[ERRO] LEXML` message, but as structured fields.
6. **Write-like tools are out of scope.** mcp-juridico-brasil's `confirmar_leitura_intimacao` has legal effect and is gated by a dry-run default plus an env var. Our MVP is read-only, so we should say so in the positioning.
7. **Positioning.**
   - Gap: open-source, container-first, remote streamable HTTP, English-facing contract, normalized citations, Brazilian primary sources. Everything I found in Brazilian space is local stdio, Portuguese-first, or proprietary.
   - Do not compete with mcp-brasil on breadth (533 tools) or jurismcp on per-court scraping depth. Compete on a stable, tested contract and deployability.
   - Avoid the proprietary name/CPF discovery use case of api.mcp.ai/legal. It is the highest LGPD risk in the sample. Our responsible-use/LGPD note should state this explicitly.
8. **Operational features worth copying.** `/health` with the deployed git SHA, Prometheus metrics not publicly exposed (CourtListener), offline fixture tests plus a separate live smoke test (eu-sparql). They match our "fakes + recorded contract tests, no network in CI" decision.
9. **Source risk.** Plan for LexML being blocked (see section 2). The MVP should degrade gracefully with a clear error, and the DataJud adapter should treat the CNJ public key as rotating (mcp-juridico-brasil says CNJ may change it at any time). Env-configured key plus a documented rotation path is the right call.

## 4. Not verified

- DataJud terms, key rotation policy and rate limits: the CNJ wiki (datajud-wiki.cnj.jus.br) returned HTTP 403 to my fetcher, so I only have the third-party claims above. Likewise, CNJ Resolution 446/2022's redistribution restriction is quoted via br-eli-mcp's README, not read at the source.
- Midpage (commercial, US): only third-party directories were found (hosted `app.midpage.ai/mcp`, OAuth, paid with trial; tool counts conflicting). No first-party docs were read, so it is not in the table.
- Other commercial vendors (Thomson Reuters, LexisNexis, vLex, Harvey, CanLII, Jusbrasil, Escavador): no first-party MCP documentation found. A GC AI blog post mentions Anthropic legal connectors in May 2026; I did not check it, and it is secondary.
- mcp-brasil: the result shape of its judiciary tools was not inspected, and its LexML coverage was not checked. jusbrasil-mcp result shapes were not inspected because the server is closed-source.
- I read READMEs and repo metadata only. No server was run, so tool counts, "verified live" corpus sizes (for example TST 3.75M rulings) and coverage figures are the authors' claims.
- Star counts, push dates and the "0 stars" figures are a one-day snapshot and say little about quality.
- Quality of the Brazilian court endpoints (undocumented REST used by jurismcp for BNP, TJES, TST) is not verified and the authors state some were obtained by portal inspection.
- Whether the geo-restriction of TRF4/TRF5 hosts affects `sa-east-1` egress.

## Sources

1. https://wiki.free.law/c/courtlistener/help/api/mcp/model-context-protocol-mcp-server-for-agentic-access
2. https://github.com/freelawproject/courtlistener-api-client (MCP_README.md, README.md)
3. https://github.com/ivancaron/jurismcp
4. https://github.com/matematicsolutions/br-eli-mcp
5. https://github.com/DeHor-Labs/mcp-juridico-brasil and https://github.com/ehrodan/lexmcp
6. https://github.com/Mcp-Brasil/mcp-brasil
7. https://github.com/mcp-dir/jusbrasil-mcp
8. https://github.com/matematicsolutions/mcp-eu-sparql
9. https://github.com/matematicsolutions/gb-eli-mcp
10. https://github.com/Ansvar-Systems/comprehensive-eu-law-mcp
