# Case-law search in competing MCP servers (issue #58, map #53)

Researched 2026-10-18. Question: how do the competing and comparable MCP servers implement case-law search, and what should a `search_publications` / `get_publication` pair on the DJEN copy or avoid? Starting point: `docs/research/mcp-benchmark.md` (on branch `docs/research-and-glossary`, not yet on `development`).

## Method and evidence labels

I downloaded the default-branch source of each open repo as a tarball on 2026-10-18 into a scratch directory and read it. Nothing was installed or run. Every claim carries one label:

- **[code]**: I read the implementing source file.
- **[docs-gen]**: I read documentation that the repo generates from its tool schemas (CourtListener `docs/mcp_tools/*.md`, header "Auto-generated ... Do not edit", with a source path per tool). Treated as near-code.
- **[README]**: only a README or other prose in the repo says so. Not checked against code.
- **[closed]**: the server is closed-source; the only evidence is the repo's manifests and docs.

One scoping fact matters for every row below: **no server I read searches the DJEN (the national Diário) from open code.** The only server with DJEN search is closed-source (Legal MCP). The "DJe" in mcp-juridico-brasil is the Domicílio Judicial Eletrônico, a per-lawyer inbox, not the public Diário. So the DJEN-specific design must come from the DJEN API research ticket, not from copying a competitor.

## 1. Answer in brief

1. **Nobody gives us a DJEN search to copy.** Legal MCP exposes `djen_search_comunicacoes` but is closed [closed]. mcp-juridico-brasil's `listar_intimacoes` is OAuth, per-lawyer, and its own code marks the endpoints as unconfirmed [code]. The remaining servers search court case-law portals (acórdãos), which is a different corpus from Publications in the Diário.
2. **Filters in open code are thin.** jurismcp and mcp-brasil take free text plus page only (STF/STJ/TST/TJES/LexML). Court, date and subject filters exist only where the source supplies them: jurismcp BNP (`tribunal`, `especie`, `numero`), jurismcp TRF4 (`origens`, `campo`), br-eli-mcp (`orgao`, `tribunal`, `tipo`). No open server filters by date range. CourtListener has `court`, `filed_after/before`, `cited_gt/lt`, `order_by` [docs-gen]. Our "subject, Court and period" entry point is therefore ahead of every Brazilian open server and has to be built on DJEN's own parameters.
3. **Paging is page-number or offset almost everywhere**, with fixed page sizes of 10 to 20 (jurismcp [code]), `pagina`/`tamanho` (mcp-brasil [code]) or none (br-eli-mcp has `limit` only [code]). Only CourtListener uses an opaque `query_id` cursor held server-side per session [code], which breaks across restarts and does not suit a stateless remote server. For us: stateless cursor that encodes the page (map #53 already lists Cursor semantics as open).
4. **Result carries ementa in all of them; full text is optional or a separate call.** Citation-ready metadata (a human-readable citation plus source URL) exists only in br-eli-mcp [code] and CourtListener.
5. **The two worst patterns to avoid**: mcp-brasil turns upstream errors into an empty result [code]; jurismcp's STF/TST tools drive headless Chrome and STJ spoofs a browser form post [code]. Both clash with ADR 0002 and with the "errors must be distinguishable from no results" rule already in the benchmark.
6. **LGPD handling is weak or absent in code.** Only mcp-brasil has a documented PII masking default, and its masking code covers its dataset layer, not the jurisprudência or DataJud tools [code, by absence]. The one open server that hashes inputs in its audit log is br-eli-mcp [code]. Party-name search is a headline feature of the closed Legal MCP [closed].

## 2. Per-server findings

### 2.1 jurismcp (ivancaron), MIT

**Tools [code].** One MCP tool per source, named after the request model class (`StjLegalPrecedentsRequest`, `TstLegalPrecedentsRequest`, `StfLegalPrecedentsRequest`, `TjesLegalPrecedentsRequest`, `LexmlLegalPrecedentsRequest`, `JurisprudenciasAiLegalPrecedentsRequest`, `BnpLegalPrecedentsRequest`, `TnuLegalPrecedentsRequest`, `Trf4LegalPrecedentsRequest`) in `src/jurismcp/presentation/mcp.py`. The tool description is the request class docstring.

**Arguments [code].**
- Every tool: `summary` (free text, required) and `page` (int, `ge=1`, default 1).
- STJ, STF: the `summary` description teaches the portal's operator grammar (`e`, `ou`, `não`, `mesmo`, `com`, `PROX(N)`, `ADJ(N)`, `$`, `?`, quotes); the STJ description alone is about 100 lines.
- TNU, TRF4: `campo` (`ementa` or `inteiro_teor`); TRF4 also `origens` (`TRF4`, `TRU4`, `TR`).
- BNP: `tribunal`, `especie` (SUM, SV, RG, RR, IRR, PUIL, IRDR...), `numero`, `incluir_cancelados`.
- Jurisprudencias.ai: `court` (required id such as `tjsp`, `carf`).
- **No date-range filter and no subject filter on any tool.** Court is encoded in the tool name, except BNP, TRF4 and Jurisprudencias.ai.

**Paging [code].** Fixed per-source page size, no `limit` argument: STJ computes `offset = (page - 1) * size + 1` and posts a form; BNP and LexML use 20 per page; eproc (TNU, TRF4) 10. The model is told in the field description to request the next page when results are relevant but insufficient.

**Result [code].** `BaseLegalPrecedent` in `domain/base.py`: `summary` (ementa, required, stripped), then nullable `full_text`, `full_text_url`, `relator_original`, `divergencia_vencedora` (bool, default False), `court`, `urn`. One MCP `TextContent` per result, each a `model_dump_json()`. For STJ the metadata header (class, relator, decision date, DJe date, indicator) is **prepended inside the `summary` string** as `[...]` [code, `stj.py`], so the field is not pure ementa. There is no process number field: the CNJ number lives only in that header text for STJ. `full_text` is only filled when the portal returns it in the same response (TJES, TNU, TRF4); otherwise a URL to the PDF or detail page.

**Long text [code].** No truncation or chunking. Full texts are returned whole.

**Failures [code].** `call_tool` catches every exception and returns a single text block `[ERRO] <TRIBUNAL>: <exc>. Tente novamente com uma query diferente ou mais simples.` An empty result is the text `Nenhum resultado encontrado`. LexML is the exception worth copying: the module detects the Senado anti-bot page and raises a specific error, with a comment that returning `[]` would read as "no case law exists" [code, `lexml.py`]. HTTP sources retry (loop with `last_error`) [code]. The error is free text, not structured, and the MCP `isError` flag is not set (the handler returns normal content).

**Browser dependence [code].** `requires_browser = True` by default; STF and TST launch patchright Chromium with `--disable-blink-features=AutomationControlled` and a spoofed Chrome user agent (`utils.py`). STJ posts to `processo.stj.jus.br/SCON/pesquisar.jsp` with browser-like `Origin` and `Referer` headers and raises on 403.

**LGPD / party names.** No mention in code or README (grep for LGPD, privacidade, parte finds nothing relevant) [code, by absence]. README warns about overloading official servers [README].

**Copy:** explicit "blocked" error instead of empty result; nullable additive fields; the BNP precedent-type vocabulary (`especie`) as a filter; `campo` ementa vs inteiro teor; `incluir_cancelados` to surface superseded precedents. **Avoid:** one tool per court; operator grammar pasted into tool descriptions; metadata mixed into the ementa string; headless Chrome and header spoofing; unstructured errors.

### 2.2 br-eli-mcp (matematicsolutions), Apache-2.0

**Tools [code].** FastMCP, `server.py`. Case-law related: `br_search_processos` / `br_get_processo` (DataJud dockets, no ruling text), `br_search_case_stj` / `br_get_case_stj`, `br_get_case_carf`, `br_search_case_tst` / `br_get_case_tst`, `br_search_case_tcu` / `br_get_case_tcu`, `br_coverage`. All annotated read-only, idempotent, non-destructive, `openWorldHint=True`.

**Arguments [code].**
- `br_search_case_stj(orgao, query, limit=20)`: `orgao` is one of ten chambers/sections (`CORTE ESPECIAL`, `PRIMEIRA TURMA`...), validated against a whitelist; `query` is a 6+ digit number (exact match on `numeroProcesso` or `numeroRegistro`) or a case-insensitive substring of `ministroRelator` or `ementa`.
- `br_search_case_tst(query, tipo="ACORDAO", limit=20)`: `tipo` is whitelisted to eight verified codes; the client doc states the backend silently ignores unknown codes, so whitelisting is deliberate (`tst_client.py` docstring).
- `br_search_processos(tribunal, query, limit)`: `tribunal` whitelisted; a 15+ digit query is an exact CNJ match, anything else matches `classe.nome`.
- **No date filter, no free-text subject filter beyond substring.** The tool docs say the legislation APIs have "no free-text keyword search" and the model must resolve identifiers first.

**Paging [code].** `limit` only; no page or cursor argument on the search tools (the TST client has a `page` argument internally but the tool does not expose it). Response is `{"total": n, "items": [...]}` where `total` is the number returned, not the corpus size.

**Source model [code].** STJ comes from the STJ Open Data CKAN portal: one monthly bulk JSON per chamber, downloaded and filtered in memory. `MAX_MONTHS_SCANNED = 6`, so a miss means "not in the last six monthly files". The tool docstring states this ("a miss means 'not in the scanned window'"). Coverage starts May 2022 [code, docstring]. TST uses the TST jurisprudence backend's JSON `pesquisa-textual` endpoint, reverse-engineered by capturing the frontend's network trace (`tst_client.py` docstring); the docstring reports an earlier version shipped filters that silently no-op'd.

**Result [code].** Each item is the parsed record plus a citation block: `human_readable_citation` (for example `STJ, <classe> <numero>, Rel. Min. <nome>, j. DD/MM/AAAA`) and `source_url`. `get_*` returns `ementa` and `decisao` (full ruling prose) for STJ. Citation formats are specified per source in the server `INSTRUCTIONS`.

**Failures [code].** A `ToolError` with a `[code]` prefix and exactly three codes: `invalid_arg`, `not_found`, `upstream_error`; each client has a mapper from httpx exceptions (404 to `not_found`, transport/status to `upstream_error`). Instructions tell the model to retry once on `upstream_error`. Clients retry 429/5xx up to 3 attempts with exponential backoff and an on-disk HTTP cache with category TTLs.

**Coverage tool [code].** `br_coverage` returns what is and is not covered; instructions tell the agent to call it when a search is empty and to "not answer past the edge of this corpus".

**LGPD / audit [code].** Every tool call appends to a local JSONL audit file, logging a hash of the input (`hash_input`), result count, duration and status, **not the query text** (`audit.py`, calls in `server.py`). `DISCOVERY.md` records that DataJud docket data can carry party information and that Resolução CNJ 446/2022 restricts bulk redistribution, so the design is live per-query lookups, short-TTL cache, no corpus persisted [README-level prose in DISCOVERY.md; the no-bulk behaviour is also visible in the code for DataJud, but for STJ the client does bulk-download monthly files into cache]. No party-name masking.

**Copy:** `[code]`-prefixed three-value error contract (we need more codes: `source_blocked`, `source_changed`, `rate_limited` per map #53); citation block on every item; `br_coverage` plus the "do not answer past the edge" instruction; whitelist enums with explicit rejection; honest "scanned window" wording; hashed-input audit. **Avoid:** `total` that means "returned count"; a six-month window hidden behind a search verb unless it is reported in the response; in-memory scan of bulk files (does not fit a stateless container); reverse-engineered undocumented backends unless pinned by contract tests.

### 2.3 mcp-juridico-brasil (DeHor-Labs), MIT

**Which "DJe".** The `dje/` module targets the Domicílio Judicial Eletrônico (`domicilio-eletronico.pdpj.jus.br`, token from `gecli.cnj.jus.br`), a per-lawyer communications inbox with OAuth2 `client_credentials` plus `DJE_BEHALF_OF_CPF` [code, `dje/client.py`]. It is not the public DJEN and not a case-law search.

**Tools [code].** `listar_intimacoes(numero_processo=None, apenas_pendentes=True, limite=50)` and `confirmar_leitura_intimacao`. The list tool filters by CNJ number (validated with `validar_numero_cnj`) and pending status only. **No court, date, subject or free-text filter; no paging beyond `limite`.**

**Result [code].** `Intimacao`: `id`, `numero_processo`, `orgao_julgador`, `tipo_comunicacao`, `data_disponibilizacao`, `data_leitura`, `prazo_em_dias`, `status`, `is_sigilosa`, `conteudo` (nullable; documented as possibly absent even when not sigilosa). Wrapper returns `total`, `pendentes` and a legal-notice string on every call.

**Sigilo [code].** Communications flagged `sigilosa` or `segredoJustica` have `conteudo` suppressed, and the provider counts omitted ones (`provider.py`). This is the only open code in the set that has a per-record confidentiality gate.

**Status of the integration [code].** The client comments say "mock-ready" and carry `INTEGRACAO:` TODOs ("confirm endpoint after the 2026-03-31 migration", "may have moved to api.pdpj.jus.br"). The paths (`/api/v1/eu`, `/comunicacoes`) are not confirmed against the real service. Treat the DJe tools as unvalidated.

**Write tool [code + README].** `confirmar_leitura_intimacao` is dry-run by default and requires both `confirmar=True` and an env flag. Out of scope for us (map #53 excludes it).

**Copy:** suppress text of confidential records and report how many were omitted; legal-notice field on responses (but as structured data, not a repeated paragraph); CNJ number validation before the call. **Avoid:** presenting a mock-tested OAuth integration as working; a disclaimer string in every payload (token cost).

### 2.4 mcp-brasil (Mcp-Brasil), MIT code

**Tools [code].** `data/jurisprudencia/tools.py`: `buscar_jurisprudencia_stf`, `_stj`, `_tst` (each `query`, `pagina=1`, `tamanho=10`), `buscar_sumulas` (`tribunal`, `query`; only STF), `buscar_repercussao_geral` (`query`, `tema`), `buscar_informativos` (implemented as a plain acórdão search for the word "informativo" when no query is given). One tool per court again, but each is a thin wrapper.

**Filters [code].** Free text only, with operator syntax described in docstrings. No date, court-organ or subject filter. `MAX_PAGE_SIZE = 50` exists in `constants.py`.

**Result [code].** The tool returns a **Markdown string** for the model, not structured data: class and number, relator, judgment date, organ, ementa truncated to 300 characters (`_format_ementa`) and a link when present. Hint line `Use pagina=N+1` when a full page came back. Full text is not offered.

**Failures [code].** `client.buscar_*` wraps the HTTP call in `try/except Exception`, logs a warning and returns `[]`, which the tool renders as "Nenhum acórdão do STJ encontrado para '...'". **A blocked or broken upstream is indistinguishable from no results.** The module docstring admits the APIs are "reverse-engineered from the courts' web interfaces" and may return HTML. The STJ call parses a JSON `documentos` key from `scon.stj.jus.br/SCON/pesquisar.jsp`, which I did not verify returns JSON, so I cannot say the tool works [unverified]. Requests send a spoofed Chrome user agent and are throttled to 20 per 60 s.

**Scale mitigation [README].** 533 tools across 70 features, with a BM25 tool-search transform to expose only relevant tools.

**LGPD [code + README].** `ACCEPTABLE_USE.md` forbids identifying or pursuing people from case parties and forbids bypassing PII masking [README]. The masking mechanism (`MCP_BRASIL_LGPD_ALLOW_PII`, `_shared/datasets/lgpd.py`) is wired into the dataset layer (TSE candidates, dados.gov.br). A search of `data/jurisprudencia` and `data/datajud` for LGPD or mask finds nothing [code, by absence], so the policy in prose is stronger than the behaviour on judicial tools.

**Copy:** a rate limiter in front of every upstream; an acceptable-use document that states what the operator may not do. **Avoid:** error swallowing; Markdown-only output; truncating the ementa at 300 chars with no way to get the rest; the 533-tool surface.

### 2.5 Legal MCP / jusbrasil-mcp (mcp-dir), closed server [closed]

All of this is from the repo's `README.md`, `docs/ferramentas.md` and `docs/privacidade-lgpd.md`; no server code is published.

- `djen_search_comunicacoes`: inputs `numero_oab`, `uf_oab`, `nome_advogado`, `nome_parte`, `numero_processo`, `sigla_tribunal`, `data_inicio`, `data_fim`, `meio`, `texto`, `pagina`, `itens_por_pagina`. This is the only competitor listing **court, date range, free text and paging on the Diário**. Described as publications/intimações in the DJEN. Whether it filters to decisions and acórdãos is not stated.
- `djen_get_certidao(hash)`: returns the URL of the PDF certidão of a communication, using the `hash` field from the search result. Suggests the DJEN result carries a `hash` we can use as a stable id for `get_publication`; confirm in the DJEN API research.
- `djen_processos_por_parte(nome_parte, ...)`: "discovery by party name", groups DJEN hits by process number. `cnpj_processos` and `cpf_processos` build on it ("grátis").
- `processos_buscar_por_nome` / `_por_documento`: scraping of court portals, async job with `job_id` and a polling tool (`processos_get_resultado`).
- `jurisprudencia_buscar(termo, tipo, max)` and `jurisprudencia_sumulas`: LexML-backed case-law search, `max` instead of paging.
- Privacy page: lists no sub-processors other than the user's LLM host and says the host receives all returned data. There is no description of masking or retention [closed].

**Copy:** the DJEN filter set (court, dates, text, process number, paging) as the baseline; `hash` as an id. **Avoid:** party-name/CPF/CNPJ discovery; it is the product's main feature and exactly what map #53 puts out of scope.

### 2.6 CourtListener MCP (Free Law Project), BSD-2-Clause

Not Brazilian, but the most mature case-law search tool in the set. Evidence is the generated tool docs and the Python source in `courtlistener/mcp/` [docs-gen, code].

**Tools.** `search` (46 optional params), `get_more_results`, `read_document`, `search_document`, `get_counts`, `get_endpoint_item`, `call_endpoint`, `get_choices`, `extract_citations`, `analyze_citations`, plus alert and docket tools. All read tools are annotated `readOnlyHint=true`.

**Search arguments [docs-gen].** `type` (opinion, docket, RECAP, judge, oral argument; default opinion), `court` (single or array, 470 choices, resolved through `get_choices` rather than listed in the schema), `q` (query string), `case_name`, `citation`, `neutral_cite`, `judge`, `filed_after`, `filed_before`, `cited_gt`, `cited_lt`, `stat_Published`/`stat_Unpublished`... (precedential status booleans), `order_by`, `fields`, `num_results` (1 to 100, default 20), `semantic`. It also has `party_name` and `atty_name` for dockets.

**Paging [code].** `search` returns `{query_id, count, results, has_more}`. `query_id` is a short UUID stored in a **server-side session** (`prepare_query_id` calls `get_session().store_query`); `get_more_results(query_id, num_results)` continues it, and returns an error naming the missing id if the session lapsed. `count` is the upstream total.

**Result trimming [code].** `fields` is client-side projection; it always keeps `opinion_id` and `cluster_opinions` "to avoid cluster_id confusion", and warns with the available field names when a requested field is missing.

**Long text [docs-gen].** Search returns metadata and snippets; the full text is a separate tool. `read_document(opinion_id | recap_document_id | cluster_id, chunk_index, chunk_size=8000)` returns the whole text with `total_chars` when no `chunk_index` is passed, or windows with `total_chunks` for one or a list of indexes. `search_document` is a grep over documents: literal, case-insensitive, up to 20 excerpts per document. This is the best long-text answer in the set.

**Token cost [docs-gen].** The generated docs estimate the `search` tool definition alone at about 3,300 tokens (46 parameters) while `read_document` is about 600. A rich filter set is paid for on every request in the model's context.

**Copy:** a search that returns ids and snippets, plus a separate read tool with chunking and `total_chars`; counts with `has_more`; a `fields` projection; choices fetched by a helper instead of inlined enums. **Avoid for a stateless remote server:** server-side query session as the paging mechanism; a 46-parameter single schema.

## 3. Comparison against the map #53 decisions

| Decision in map #53 | What competitors show | Implication |
|---|---|---|
| `search_publications` / `get_publication` as new tools, distinct from `search_cases` | br-eli-mcp separates docket (`br_search_processos`) from ruling text (`br_search_case_*`) and says so in the docstring [code]; CourtListener separates search from read [docs-gen] | Supported. Keep Publication (text, release date) apart from Case (CNJ, movements). |
| Entry point: subject, Court and period | Open Brazilian servers have no date filter; only closed Legal MCP lists `data_inicio`/`data_fim` [closed] | We would be first among open servers; needs DJEN parameters confirmed. |
| Entry point: list Publications of a CNJ number | `djen_search_comunicacoes(numero_processo)` [closed]; `listar_intimacoes(numero_processo)` [code]; br-eli-mcp `get_*` by number [code] | Common pattern; validate the CNJ number locally first (juridico-brasil does [code]). |
| Only decisões, acórdãos, ementas | Legal MCP returns "publicações/intimações" without that cut [closed]; mcp-juridico-brasil returns all communication types [code] | No competitor filters by act type on the Diário. We need a type field on the result and an upstream or local filter; check DJEN parameters. |
| `list_coverage` and explicit `not_covered`, no fallback | br-eli-mcp `br_coverage` plus the "do not answer past the edge" instruction [code] | Direct precedent. Copy the instruction text pattern. |
| Error mapping `source_blocked`, `source_changed`, `rate_limited` | br-eli-mcp has three codes [code]; jurismcp has an ad hoc LexML blocked error [code]; mcp-brasil swallows errors [code] | Extend br-eli-mcp's `[code]` model; never return an empty list on failure. Raise them as MCP tool errors (br-eli-mcp raises an exception from the tool, which FastMCP reports as an error; jurismcp and mcp-brasil return ordinary text content). |
| Cursor and per-page cap | Fixed 10 to 20 per page [code]; `limit` only [code]; CourtListener cap 100 and server-held `query_id` [code] | Choose a stateless cursor and a hard cap (CourtListener's 100 is an upper reference; most competitors use 10 to 20). |
| LGPD of party names | Closed Legal MCP markets party-name discovery [closed]; mcp-brasil forbids it in prose [README] and masks only datasets [code]; br-eli-mcp hashes inputs in its audit log [code]; juridico-brasil suppresses confidential content [code] | No open competitor masks party names in judicial text. Decision still open in map #53; see section 4. |

## 4. Recommendations

Copy:
1. Search returns identifiers, court, dates, ementa and a source URL; a separate `get_publication` returns the full text, with `total_chars` and chunking for long text (CourtListener `read_document`, 8,000-character default window [docs-gen]).
2. Every item carries a `human_readable_citation`-style field and `source_url` (br-eli-mcp [code]).
3. Three-or-more-value structured error contract with a `[code]` and explicit `source_blocked` (br-eli-mcp plus jurismcp LexML [code]).
4. A `list_coverage` tool and a server instruction not to claim absence when coverage is missing (br-eli-mcp [code]).
5. Whitelist enums for court and publication type, with explicit rejection; unknown values must not pass through silently (br-eli-mcp TST `DOC_TYPES` [code]).
6. Confidential records: omit the text and count the omissions (juridico-brasil [code]).
7. Audit by input hash, not by query text (br-eli-mcp [code]).
8. Rate limiter and retry with backoff for 429 and 5xx (mcp-brasil, br-eli-mcp [code]).

Avoid:
1. Returning an empty result on an upstream failure (mcp-brasil [code]).
2. One tool per court, and operator grammar in tool descriptions (jurismcp [code]).
3. Headless browsers or spoofed user agents (jurismcp, mcp-brasil [code]); ADR 0002 already excludes them.
4. Party-name, CPF or CNPJ discovery (Legal MCP [closed]).
5. Server-side session cursors (CourtListener [code]) and a very wide single-tool schema (CourtListener `search`, about 3,300 tokens [docs-gen]).
6. Metadata mixed into the ementa field (jurismcp STJ [code]) and `total` meaning "returned count" (br-eli-mcp [code]).

On party names (the map's open LGPD item): no competitor offers a mask I can copy for judicial text. mcp-brasil states a masking policy and ships it only for datasets [code]. What the evidence supports is a prose and instruction layer: say in the tool description and `ACCEPTABLE_USE`-style document that results can contain personal data, avoid search-by-party, and keep logs free of query text. Whether to mask in output is a decision for the LGPD ticket, not something a competitor settles.

## 5. Not verified

- **The DJEN API itself.** I did not read its parameters, paging, result fields, terms or whether it carries the CNJ number reliably; those belong to the DJEN API tickets under map #53. A direct fetch of `comunicaapi.pje.jus.br/swagger/v1/swagger.json` returned a 404 page. Everything said above about DJEN comes from the closed Legal MCP's README/docs.
- **Legal MCP behaviour.** Closed source; arguments and claims ("free", "no captcha") are the vendor's.
- **mcp-brasil and jurismcp endpoints.** I read how they call the courts, not whether the calls work today. The jurismcp README documents the LexML block from 2026-09-29; I did not test it.
- **br-eli-mcp's DataJud client** was read only for the tool surface (`search_processos`); I did not read `caselaw_client.py` in full.
- **The CourtListener `search` result shape** (snippets) comes from the generated parameter docs and `search_tool.py`; I did not read the result field list in detail.
- **mcp-juridico-brasil DJe** was read as code, but the real service was not called; its endpoints are flagged unconfirmed by its own authors.
- **Maintenance and star counts** are in the benchmark; not re-checked.

## Sources

Default-branch snapshots read 2026-10-18 (tarballs from the GitHub API):

1. https://github.com/ivancaron/jurismcp (`src/jurismcp/presentation/mcp.py`, `domain/base.py`, `domain/stj.py`, `domain/lexml.py`, `domain/eproc.py`, `domain/bnp.py`, `utils.py`, `README.md`)
2. https://github.com/matematicsolutions/br-eli-mcp (`src/br_eli_mcp/server.py`, `stj_client.py`, `tst_client.py`, `audit.py`, `DISCOVERY.md`, `SOURCES.md`)
3. https://github.com/DeHor-Labs/mcp-juridico-brasil (`src/mcp_juridico_brasil/dje/{tools,client,provider,schemas}.py`, `README.md`)
4. https://github.com/Mcp-Brasil/mcp-brasil (`src/mcp_brasil/data/jurisprudencia/{tools,client,constants}.py`, `_shared/http_client.py`, `settings.py`, `ACCEPTABLE_USE.md`, `README.md`)
5. https://github.com/mcp-dir/jusbrasil-mcp (`README.md`, `docs/ferramentas.md`, `docs/privacidade-lgpd.md`)
6. https://github.com/freelawproject/courtlistener-api-client (`docs/mcp_tools/*.md` generated from tool schemas, `courtlistener/mcp/tools/{search_tool,get_more_results_tool,utils}.py`)
