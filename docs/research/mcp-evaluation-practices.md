# Research: how MCP servers are evaluated, and what to adopt with assayer

Researched 2026-10-22. Follow-up to an earlier shallow pass (4 searches, summaries only).
Questions: who evaluates MCP servers and how; which layers are measured (and whether
retrieval is scored separately); how live sources and non-determinism are handled; what
the legal / high-risk domain does; what juris-bridge-mcp should adopt, in which order,
with the `assayer` library.

Method: primary sources only (arXiv abstract or HTML pages, the maintainers' own docs and
READMEs, Anthropic engineering posts). Pages were opened with WebFetch, which returns a
model-written extract of the page, not raw text. Tags: `[V]` verified on 2026-10-22 (the
source was opened and the claim read in it), `[U]` unverified (seen only in a search
snippet, a secondary summary, or not readable; do not treat as a finding). Where a
section of a page was cut off by the fetcher, that is said. Nothing was run against a
live MCP server.

## Summary

- Public MCP benchmarks (MCP-Universe, LiveMCPBench, MCP-Bench, MCPEval) evaluate **agents
  and models using MCP servers**, not a single server in isolation. All of them score the
  end result (task success) and most add trajectory-level scores. [V]
- Four layers recur: (a) tool-call correctness (name validity, schema compliance, match
  to a reference call sequence), (b) task outcome checked by deterministic evaluators
  and/or an LLM judge, (c) efficiency (steps, tokens, tool errors), (d) tool-description
  quality (two 2026 papers). [V]
- **No MCP benchmark opened here reports a separate retrieval metric** (context
  precision/recall). LiveMCPBench reports that tool-retrieval errors cause nearly half
  of failures, but that is retrieval of *tools*, not of documents. Retrieval is scored
  separately in legal RAG work (LegalBench-RAG), which is where to borrow it. [V for the
  absence in the abstracts and sections read; the full papers were not read end to end]
- Live sources are handled three ways: **dynamic evaluators** that fetch ground truth at
  eval time (MCP-Universe), **LLM judge that accepts several valid answers** (LiveMCPBench),
  and **record/replay cassettes** (mcp-recorder, mock-mcp). Anthropic's guidance adds
  repeated trials, isolation and judge calibration against humans. [V]
- Legal domain: the Stanford RegLab/HAI study gives the reference taxonomy
  (correct/incorrect/refusal x grounded/misgrounded/ungrounded) and a human-labelling
  protocol (kappa 0.77). It also says the tools' own automated self-checking was unsuitable
  for the evaluation. No Brazilian benchmark of fabricated case-law citations was found. [V / not found]
- Recommended order for this project: deterministic checks on recorded fixtures first
  (tool name, args, schema, result shape, citation exists in the result), then retrieval
  metrics on a small golden set, then judge-based faithfulness calibrated on a human-labelled
  sample, and opt-in live runs last. See section 5.

## 1. Who evaluates MCP servers, and how

### Benchmarks

| Benchmark | What it is | How it scores | Source |
|---|---|---|---|
| MCP-Universe (Salesforce) | 6 domains, 11 real MCP servers; long-horizon tasks | "Execution-based evaluators": **format** (output format), **static** (content that does not change), **dynamic** (fetches live ground truth for time-sensitive tasks). Headline: success rate (GPT-5 43.72%) | [1][2] [V] |
| LiveMCPBench | 95 daily tasks, 70 servers, 527 tools; multi-server routing | LLM-as-a-judge that checks task outcome and is meant to handle "dynamic data sources and multiple valid solution paths". Success rate (best 78.95%) | [3] [V, abstract only] |
| MCP-Bench (Accenture) | 28 live servers, 250 tools in the abstract (a Hugging Face page says 31; not reconciled) | Rule-based: tool-name validity, schema compliance, execution success. LLM judge (o4-mini default): task completion, tool usage, planning, each 1-10 | [4][5] [V] |
| MCPEval (Salesforce) | Auto-generates tasks from tool specs, verifies them with a frontier agent, keeps ground-truth trajectories | Tool-call matching (strict: exact names, params, order; flexible: params >= 0.6, order >= 0.5; default weights 0.4/0.4/0.2) plus an LLM judge for trajectory and completion on 0-1 | [6] [V] |

Details worth reusing:

- MCP-Universe evaluators are declarative: `op(func(response), value)` with `func`
  helpers (`json`, `get`, `len`, `foreach`) and tasks as JSON files with `question`,
  `mcp_servers`, `output_format`, `evaluators`. The README recommends a dedicated test
  GitHub account because agents perform real operations. It does not detail how dynamic
  evaluators work. [2] [V]
- MCP-Bench's schema-compliance metric only counts calls whose tool name is valid, and
  its judge is run five times with shuffled rubric order, averaging the results. [4] [V]
- MCPEval states its own limits: synthetic data, judge cost on long trajectories, possible
  false ground truth from automated verification, and reference bias because the ground
  truth comes from gpt-4.1. [6] [V]

### Frameworks and their documented MCP support

| Framework | What the docs say about MCP | Source |
|---|---|---|
| Inspect AI | Documented MCP support: `mcp_server_stdio()`, `mcp_server_http()`, `mcp_server_sandbox()`; `mcp_tools()` filters tools; servers are a `ToolSource` passed to `react(tools=...)`; calls go through the approval policy when `execution="local"`. MCP is a way to give an agent tools, not an MCP-server test suite. Model-graded scorers exist (`model_graded_qa`, `model_graded_fact`); epoch reducers include `mean`, `median`, `mode`, `max`, `pass_at_{k}`, `at_least_{k}` | [7][8][9] [V] |
| promptfoo | An `mcp` provider that **calls MCP tools directly** (stdio, URL, several servers; bearer/basic/API key/OAuth), prompts are JSON tool calls, so the server itself can be asserted on (`contains`, `is-json`, `javascript`). For chat providers with `mcp.enabled`, executed calls appear in `metadata.toolCalls` for assertions. Red-team plugins in the examples (`pii`, `bfla`, `bola`, `sql-injection`) | [10] [V] |
| DeepEval | First-class MCP model: `MCPServer`, `MCPToolCall`/`MCPResourceCall`/`MCPPromptCall`, `LLMTestCase(mcp_servers, mcp_tools_called, ...)`. `MCPUseMetric` (LLM judge of primitives chosen and arguments; modes `llm`, `hybrid`, `system_one`; single-turn). Multi-turn and task-completion metrics exist but the page opened did not describe them (class names are inconsistent across the docs) | [11][12] [V] |
| LangSmith | Documents **trajectory evaluation** (reference-trajectory match in `strict`, `unordered`, `subset`, `superset` modes, no extra LLM call; LLM-as-judge trajectory, with or without a reference). The page opened mentions MCP only to say the docs themselves can be reached over MCP. No MCP-server-evaluation guide was found. | [13] [V for the page; absence of a guide is U] |
| Langfuse | Documents **MCP tracing** only: OpenTelemetry context passed in MCP `_meta` so client and server traces link. The page documents no MCP-specific evaluation. | [14] [V] |

Not confirmed: whether LangSmith or Langfuse have any MCP-specific evaluator elsewhere in
their docs (only one page each was read). A search result mentions Confident AI MCP
metrics; not opened. [U]

## 2. Layers evaluated

| Layer | Evidence | Notes |
|---|---|---|
| Tool-call correctness: name, args, schema | MCP-Bench (name validity, schema compliance) [4]; MCPEval (name/param/order match) [6]; DeepEval `MCPUseMetric` (argument validity) [11]; LangSmith trajectory match [13]; Anthropic suggests recording expected tools but "avoid overspecifying" since several paths can be valid [15] | The only layer that is fully deterministic. [V] |
| Task outcome / results | MCP-Universe static + dynamic evaluators [1][2]; LiveMCPBench judge [3]; MCP-Bench task-completion judge [4]; Anthropic: pair each prompt with a verifiable outcome, avoid overly strict verifiers [15] | [V] |
| Retrieval as a separate metric | **Not found in the four MCP benchmarks.** MCP-Bench judges "information grounding" as a sub-dimension of task completion [4]; LiveMCPBench counts tool-retrieval errors (about half of failures) [3]. In legal RAG, LegalBench-RAG is "the first benchmark specifically designed to evaluate the retrieval step", rewarding small precise spans [16] | The exact LegalBench-RAG metrics (a secondary summary says document-level and character-level precision/recall) were not confirmed in a primary page. [U] |
| Faithfulness / hallucination | Stanford typology (section 4) [17]; MCP-Bench grounding and MCPEval completion-accuracy judges are generic, not citation-level [4][6] | [V] |
| Efficiency | Anthropic: track accuracy, tool and task runtime, number of tool calls, total tokens, tool errors; read transcripts: redundant calls hint at pagination/limit tuning, repeated invalid-parameter errors hint at unclear descriptions [15]. MCP-Universe: tokens grow fast with steps [1]. MCP-Bench judges parallelism/efficiency [4] | [V] |
| Robustness / errors | MCP-Bench "execution success" (calls without runtime failure) [4]; Anthropic counts tool errors [15]; promptfoo red-team plugins for security [10] | No benchmark opened tests malformed upstream responses or outages. [V for the absence in what was read] |
| Quality of tool descriptions | "MCP Tool Descriptions Are Smelly!": 856 tools in 103 servers, 97.1% had at least one smell, 56% did not state purpose clearly; augmenting descriptions raised median task success 5.85 points but steps +67.46%, with regressions in 16.67% of cases [18]. "From Docs to Descriptions": 4 dimensions (accuracy, functionality, completeness, conciseness), 18 smell categories, 10,831 servers; functionality and accuracy smells had the largest effect on tool selection [19] | Abstracts only. [V for the abstracts] |

## 3. Live sources and non-determinism

- **Dynamic ground truth.** MCP-Universe re-fetches ground truth at eval time for
  time-sensitive tasks; the abstract and README do not say how. [1][2] [V]
- **Judge instead of fixed answer.** LiveMCPBench lets a judge accept several valid
  outcomes over changing data; no judge-agreement figure appeared on the abstract page. [3] [V]
- **Tool-call caching.** MCP-Bench ships a tool-call cache directory and `tool_cache.py`;
  the README does not document keys or expiry. Judge model is hard-coded (o4-mini) for
  reproducibility. [5] [V]
- **Record/replay.** `mcp-recorder` stores JSON-RPC messages in a cassette; modes record,
  replay ("no real server, no credentials, no network") and **verify** (replays recorded
  requests against an updated server and exits non-zero on diff; supports ignoring volatile
  fields; `--update` refreshes). Matching: `method_params` (default, ignores `_meta`),
  `sequential`, `strict`. [20] [V] `mock-mcp` records tool calls, results and the tool
  manifest into a JSONL cassette and positions itself for evaluating agent skills without
  the real server. [21] [V] Others (`mcp-replay`, `mcp-rec`, `@mcp-testing/server-tester`)
  were seen only in search results or blocked (npm returned 403). [U]
- **Repeated trials.** Anthropic: "a task that passed on one eval run might fail on the
  next", so run several trials; pass@k fits tools where one success is enough, pass^k fits
  cases needing consistency; isolate each trial in a clean environment; a 0% pass rate is
  usually a broken task or grader. [22] [V] Inspect offers epoch reducers `pass_at_{k}`
  and `at_least_{k}`. [9] [V]
- **Judge calibration.** Anthropic: LLM judges "should be closely calibrated with human
  experts", give the judge an "Unknown" exit, grade each dimension with an isolated judge,
  grade the output not the path. [22] [V] MT-Bench paper: strong judges match human
  preferences about as well as humans agree with each other, but show position, length and
  self-preference biases. [23] [V] MCP-Bench mitigates rubric-order bias with five shuffled
  judge runs. [4] [V] Stanford measured human inter-coder agreement (kappa 0.77). [17] [V]
- **Opt-in live runs.** No source opened documents an explicit "opt-in live mode" flag.
  Closest: mcp-recorder's `verify --target` runs against a live server on demand [20], and
  MCP-Universe requires per-service credentials and recommends a dedicated test account [2].
  The opt-in convention is therefore our own design, not a found practice. [V that none was
  found in the sources read]

## 4. Legal / high-risk domain

- **Stanford RegLab/HAI, "Hallucination-Free?"** (Magesh et al., arXiv 2405.20362):
  preregistered evaluation of Lexis+ AI, Westlaw AI-Assisted Research and Ask Practical Law
  AI. The abstract reports 17% to 33% hallucination for Lexis+ and Westlaw tools; the HAI
  news page says Lexis+ AI and Ask Practical Law AI over 17% and Westlaw over 34% (the two
  texts do not match exactly; both are the authors' own). [17][24] [V]
  - Typology (full text): each response is coded on *correctness* (correct, incorrect,
    refusal) and, for correct ones, *groundedness* (grounded, misgrounded, ungrounded).
    Hallucinated = incorrect or misgrounded; accurate = correct and grounded; incomplete =
    refusal or ungrounded. A refusal saying no pertinent source exists is correct for a
    false-premise question. [17] [V]
  - Dataset: 202 queries (general research 80, jurisdiction/time-specific 70, factual recall
    30, false premise 22), preregistered 2024-03-22. Three expert labelers; a fourth coded 48
    responses blind (kappa 0.77, 85.4% agreement). The authors say automated self-checking
    by the tools was unsuitable for evaluation. [17] [V]
  - RAG-specific error sources named by HAI: retrieval failures, retrieval of inapplicable
    authority (for example an overturned standard), sycophancy toward a false premise. [24] [V]
  - Access limits: Thomson Reuters denied three access requests initially. The limitations
    section on non-determinism was cut off in the fetch and was not read. [17] [V / U for the rest]
- **"Large Legal Fictions"** (arXiv 2401.01301): general-purpose models hallucinated 58%
  (ChatGPT 4) and 88% (Llama 2) on verifiable questions about random federal cases; models
  often fail to correct false legal premises. [25] [V]
- **LegalBench-RAG** (arXiv 2408.10343): retrieval-step benchmark, 6,858 query-answer pairs
  over 79M+ characters, expert-annotated, built by tracing LegalBench context back to source
  passages; argues precise spans enable citations. Metrics not stated on the abstract page. [16] [V]
- **Brazil.** OAB-Bench (Pires, Malaquias Junior, Nogueira, arXiv 2504.21202): 105 bar-exam
  questions, seven areas, official rubric, with an LLM-judge study where o1 correlated
  strongly with human scores. Seen in a search result only. [26] [U] "Na Pratica, qual IA
  Entende o Direito?" (Marinho et al., arXiv 2510.18108) compares general-purpose AIs and a
  Brazilian legal AI; the PDF body could not be decoded, so its method is unknown. [27] [U]
  **No benchmark of fabricated Brazilian case-law citations (inexistent acordaos, wrong
  numbers) was found.** Press cases of fines for fake case law exist but were seen only on
  commercial blogs and were not used. [not confirmed]

## 5. Application to juris-bridge-mcp with assayer

Fit: juris-bridge is a read-only retrieval server (DJEN publications, BNP precedents). The
published MCP benchmarks test agent planning over many tools; our server has few tools, so
the useful parts are the deterministic layers, the retrieval metrics, and the legal
faithfulness taxonomy. assayer already has the matching primitives (Runner, Dataset/Case,
Trajectory, agent metrics for tool correctness and arguments, retrieval context
precision/recall, faithfulness to retrieved context via an injected Judge, k-repetition with
pass@k and pass^k, LangSmith/Langfuse adapters). The mapping below is our proposal, not a
sourced practice.

Order (cheapest and most deterministic first):

1. **Tool-call correctness on recorded fixtures (no LLM, no network).** Cases with expected
   tool name and arguments; schema compliance and name validity as in MCP-Bench [4]; keep
   expected-tool checks loose enough for alternative paths [15]. Record real DJEN/BNP
   responses once into cassettes (mcp-recorder style [20]) and replay in CI; use `verify`
   semantics (diff on a live target, ignore volatile fields) as the regression check.
2. **Result-shape and citation-existence checks (deterministic).** Each cited CNJ number /
   precedent id in an answer must appear in the tool results of the same Trajectory. This is
   the cheap proxy for Stanford's "misgrounded" and for fabricated citations. Whether
   assayer has this metric built in was not checked beyond README/GLOSSARY; may need a
   custom Metric.
3. **Retrieval metrics on a small golden set.** Label, per query, the publications or
   precedents that should be returned; score context precision/recall with assayer. This
   fills the gap no MCP benchmark covers; LegalBench-RAG [16] is the conceptual precedent
   (small precise spans over whole documents). Golden sets must be dated, since DJEN is a
   moving source.
4. **Faithfulness with an LLM judge, calibrated.** Use the Stanford rubric (correct /
   incorrect / refusal x grounded / misgrounded / ungrounded) [17]; label 40 to 50 answers by
   a human (the 48-response, kappa 0.77 audit is the benchmark of effort), measure judge
   agreement before trusting it [22][23], allow "Unknown", one judge per dimension, repeat
   judge runs [4].
5. **Consistency.** Run each Case k times; report pass^k for lookups where a wrong
   answer is costly and pass@k only for exploratory search [22].
6. **Efficiency and description quality.** Track calls, tokens, tool errors per Case [15];
   treat repeated invalid-argument errors as a signal to fix tool descriptions, and review
   descriptions against the smell dimensions [18][19].
7. **Opt-in live runs.** A separate, explicitly enabled suite against the real DJEN/BNP
   (rate limits, honest behaviour, the project's read-only rules), used to refresh
   cassettes and detect upstream drift, never in default CI. This is our design; no source
   prescribes it.

Adapters: assayer can export to LangSmith and Langfuse. Langfuse's MCP tracing page
documents trace linking only [14]; no MCP-specific evaluator was found in either backend.

## What was NOT confirmed

- LiveMCPBench and MCP-Universe: only abstract pages and the README were read; judge
  agreement, dynamic-evaluator implementation and per-category error analysis are unknown.
- MCP-Bench: only the first 100k of 168k characters of the paper HTML was read.
  MCPEval: first 100k of 131k.
- LangSmith and Langfuse: no MCP-server evaluation feature found, but only one page each
  was read; absence is not proven.
- DeepEval multi-turn and task-completion MCP metrics: not described in the pages read.
- Inspect AI: epochs reducers verified; whether Inspect has an MCP-server-under-test
  pattern (as opposed to MCP as agent tools) was not found.
- Retrieval metrics in LegalBench-RAG (exact definitions), OAB-Bench details, and the
  content of arXiv 2510.18108: not read in a primary text.
- `mcp-replay`, `mcp-rec`, `@mcp-testing/server-tester`: search snippets or blocked page.
- Stanford limitations on non-determinism: fetch truncated.
- Any Brazilian evaluation of fabricated citations / DJEN / BNP-based tools: none found.
- Any documented "opt-in live execution" convention: none found.

## Sources

1. MCP-Universe, arXiv abstract. <https://arxiv.org/abs/2508.14704>
2. MCP-Universe repository README. <https://github.com/SalesforceAIResearch/MCP-Universe>
3. LiveMCPBench, arXiv abstract. <https://arxiv.org/abs/2508.01780>
4. MCP-Bench, arXiv HTML. <https://arxiv.org/html/2508.20453>
5. MCP-Bench repository README. <https://github.com/Accenture/mcp-bench>
6. MCPEval, arXiv HTML. <https://arxiv.org/html/2507.12806v1>
7. Inspect AI, MCP tools. <https://inspect.aisi.org.uk/tools-mcp.html>
8. Inspect AI, scorers. <https://inspect.aisi.org.uk/scorers.html>
9. Inspect AI, metrics and epoch reducers. <https://inspect.aisi.org.uk/metrics.html>
10. promptfoo, MCP provider. <https://www.promptfoo.dev/docs/providers/mcp/>
11. DeepEval, MCP Use metric. <https://deepeval.com/docs/metrics-mcp-use>
12. DeepEval, evaluating MCP. <https://deepeval.com/docs/evaluation-mcp>
13. LangSmith, trajectory evaluations. <https://docs.langchain.com/langsmith/trajectory-evals>
14. Langfuse, MCP tracing. <https://langfuse.com/docs/observability/features/mcp-tracing>
15. Anthropic, Writing tools for agents. <https://www.anthropic.com/engineering/writing-tools-for-agents>
16. LegalBench-RAG, arXiv abstract. <https://arxiv.org/abs/2408.10343>
17. Magesh et al., Hallucination-Free?, arXiv HTML. <https://arxiv.org/html/2405.20362> (abstract: <https://arxiv.org/abs/2405.20362>)
18. MCP Tool Descriptions Are Smelly, arXiv. <https://arxiv.org/abs/2602.14878>
19. From Docs to Descriptions, arXiv. <https://arxiv.org/abs/2602.18914>
20. mcp-recorder README. <https://github.com/devhelmhq/mcp-recorder>
21. mock-mcp README. <https://github.com/dotutils/mock-mcp>
22. Anthropic, Demystifying evals for AI agents. <https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents>
23. Zheng et al., Judging LLM-as-a-Judge (MT-Bench), arXiv. <https://arxiv.org/abs/2306.05685>
24. Stanford HAI news on the study. <https://hai.stanford.edu/news/ai-trial-legal-models-hallucinate-1-out-6-or-more-benchmarking-queries>
25. Dahl et al., Large Legal Fictions, arXiv. <https://arxiv.org/abs/2401.01301>
26. OAB-Bench, arXiv (search result only, [U]). <https://arxiv.org/abs/2504.21202>
27. Marinho et al., arXiv 2510.18108 (metadata only, [U]). <https://arxiv.org/abs/2510.18108>
