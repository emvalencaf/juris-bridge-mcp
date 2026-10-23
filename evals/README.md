<a id="readme-top"></a>

<br />
<div align="center">
  <h3 align="center">Juris Bridge MCP evaluation</h3>

  <p align="center">
    Puts Eval cases to an agent connected to the server and scores what the agent did.
    Run by hand; it informs and never gates a merge or a release.
    <br />
    <a href="../docs/adr/0009-assayer-with-own-agent-loop.md"><strong>Why assayer »</strong></a>
    <br />
    <br />
    <a href="https://github.com/emvalencaf/juris-bridge-mcp/issues/90">Spec (#90)</a>
    &middot;
    <a href="https://github.com/emvalencaf/juris-bridge-mcp/issues/new">Report Bug</a>
  </p>
</div>

<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
    <li><a href="#acknowledgments">Acknowledgments</a></li>
  </ol>
</details>

## About The Project

This directory evaluates the server with an agent. It lives beside the
`juris_bridge_mcp` package, outside it and outside `tests/`, so the published
package, the default `pytest` run and the CI never see it. The Eval case and
Cassette terms are defined in [GLOSSARY.md](../GLOSSARY.md); the full goals are in
the [spec (#90)](https://github.com/emvalencaf/juris-bridge-mcp/issues/90).

The first end-to-end slice works: the agent loop, a tool-use Score and a seed set run
offline against seed Cassettes. Recording, the other metrics and the judge arrive in later
tickets of the spec.

| Path | Holds |
|---|---|
| `__main__.py` | The command (`python -m evals run`) |
| `agent.py` | The agent loop: lists the server's real tools, converts them for the model, loops model, tool calls and results, and returns an assayer Trajectory |
| `run.py` | `run_eval`: Eval cases to an Experiment (one Cassette, session and Trajectory per case); `format_experiment` |
| `consistency.py`, `report.py`, `store.py`, `compare.py` | All-pass / at-least-one by case kind and efficiency; the report with its limits; saving and loading a run; comparing two runs |
| `tool_use.py` | The `tool_use` Metric, loose on the route |
| `judge.py` | The rubric judge Metric (opt-in `--judge`): correctness by grounding, repeated, uncalibrated |
| `citation_existence.py` | The `citation_existence` Metric: each CNJ number or Precedent cited in the answer must appear in a tool result |
| `draft_precedents.py` | Records the drafts about Precedents, negatives and Coverage from the live BNP (`python -m evals.draft_precedents`) |
| `seed.py` | Builds the seed Cassettes from the test fixtures |
| `dataset.py` | Loads Eval cases from the split folders |
| `redaction.py` | `Redactor` / `redact()`: replaces personal data in Source text with placeholders (NER names numbered `[PESSOA N]`, `[CPF]`, `[CNPJ]`) | |
| `cassette.py` | The Cassette format and the transport that replays it in place of the network; a request with no recording is a counted miss answered as `source_unavailable` |
| `record.py` | Record mode: `record_case()` forwards the server's requests to the live Sources (opt-in), redacts and paces them, and saves a Cassette |
| `cassettes/` | One `<case id>.json` Cassette per Eval case, with its recording date |
| `cases/tuning/`, `cases/validation/`, `cases/drafts/` | Eval cases as plain JSON lists, split by folder; drafts count toward no result |
| `cases/seed/` | Three fictitious Eval cases that run against the seed Cassettes; they count toward no result |
| `llm/` | The `LLMClient` Protocol, the Gemini client, rate limits, settings and test doubles |
| `tests/` | Tests of the evaluation itself, run on request only |
| `results/` | Local results; git-ignored |

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Built With

* [assayer](https://github.com/emvalencaf/assayer) (`llm-assayer-eval`, import name `assayer`)
* [uv](https://docs.astral.sh/uv/) dependency groups

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Getting Started

### Prerequisites

* Python 3.12 or newer and [`uv`](https://docs.astral.sh/uv/)

### Installation

assayer sits in the `evals` dependency group of `pyproject.toml`, separate from
`dev`. A plain `uv sync` or `uv run --dev ...` (what the CI uses) does not install
it; ask for it with `--group evals`.

```bash
uv sync --group evals
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Usage

From the repository root:

```bash
uv run --group evals python -m evals run --split seed
```

It loads the Eval cases of the split (`tuning` by default; an empty split prints an empty
Experiment and needs no model), puts each to the agent over the Cassette named after its id,
and prints the Experiment: per Eval case the `tool_use` Score, the number of tool calls and
errors, the tokens and the cassette misses. The model is built from the settings below, so
`GEMINI_API_KEY` and the `EVALS_*` variables must be set. To run the tests of the evaluation
itself (the default `pytest` run skips them; they use a scripted model and never reach Gemini
or a Source):

```bash
uv run --group evals pytest evals
```

### Eval case

A JSON list per file under `cases/<split>/`, in the format of assayer's case loader:

```json
{
  "id": "seed-precedent-rg-1002",
  "input": "Qual é a tese fixada no Tema 1002 da repercussão geral do STF?",
  "expected_tool_calls": [
    {"any_of": [
      {"name": "search_precedents", "arguments": {"number": "1002", "kind": "RG"}},
      {"name": "get_precedent", "arguments": {"id": "stf-rg-1002"}}
    ]}
  ],
  "reference_context_ids": ["stf-rg-1002"],
  "expected_outcome": "States the thesis of theme 1002 as the tool returned it."
}
```

* `id` names the Cassette (`cassettes/<id>.json`); `input` is the question.
* `expected_tool_calls` are requirements, each a tool name, `{"name", "arguments"}`
  (`name` may be a list of equally good tools) or `{"any_of": [...]}` for alternative routes.
* `reference_context_ids` are the Publication CNJ numbers or Precedent ids that retrieval will
  be scored against (a later ticket); `expected_outcome` says in words what a good answer does.

### Agent and tool-use Score

`evals.agent.run_agent(question, session, llm, ...)` lists the tools of the real server over the
in-memory client of a `ReplaySession`, converts their JSON Schema to the OpenAPI subset the model
accepts (`to_declaration`), and loops until the model answers or `max_steps` model calls. Every
tool call, its arguments, result or error, the final answer and the tokens go into the
Trajectory; the cassette-miss count is its `final_state`. The tools offered are those of
`IN_SCOPE_TOOLS` (Publications, Precedents and `list_coverage`).

The `tool_use` Metric is looser than assayer's `tool_correctness` and `tool_argument_match`:
each expected call is met by the best matching call of the Trajectory, arguments are compared
only on the keys the Eval case lists (strings ignoring case and surrounding space), and extra
calls or another route listed with `any_of` are never marked wrong. The Score is the mean over
the requirements. Seed Cassettes are rebuilt with `uv run --group evals python -m evals.seed`.

### Rubric judge

`python -m evals run --split seed --judge` also asks the judge model (`EVALS_JUDGE_MODEL`) to grade
each answer. It is opt-in: without `--judge` no judge call is spent. The `judge` Metric
(`evals.judge.make_rubric_judge`, an assayer judge-based Metric over `LLMClientJudge`, which adapts
an `LLMClient` to assayer's `Judge`) gets the question, the expected outcome, the tool results and the
final answer, and rates the Stanford legal-AI rubric: correctness (`correct`, `incorrect`, `refusal`)
and grounding (`grounded`, `misgrounded`, `ungrounded`). It may answer `unknown`; output that is not
valid JSON, or uses another label, counts as `unknown` and never crashes the run.

Each judgment is repeated three times (`make_rubric_judge(judge, repetitions=N)`), so a run spends
3 judge calls per case. The report shows the majority verdict, the count per label and the
agreement per axis. A tie is `unknown`. The Score value is the share of repetitions that were correct
and grounded. The verdict is stored in the Score's `metadata` (`correctness`, `grounding`, `counts`,
`agreement`, `repetitions`, `uncalibrated`, `prompt`, `prompt_hash`) for the calibration to read.

Results are marked `[UNCALIBRATED]` until a measured calibration record exists at
`evals/results/calibration.json` (`evals.judge.load_calibration` reads it; absent, unreadable or
without `"measured": true` means uncalibrated). Do not read an uncalibrated verdict as a measure of
the server. See "Calibrating the judge" below.

### Calibrating the judge

The judge is checked against your own labels, using a stronger model (`EVALS_CALIBRATION_MODEL`).

```bash
python -m evals calibrate export RUN [--n 20] [--out FILE]   # default: results/calibration-labels.json
# ... label the file by hand ...
python -m evals calibrate score RUN LABELS
```

`RUN` is a saved run (a path or a file name under `evals/results/`). `export` samples about 20
answers, the same ones every time and spread across the Eval cases, and never writes the judge's
verdict, so you label blind. `score` re-judges the labelled answers with the calibration model,
prints the agreement with your labels (per axis and joint, with Cohen's kappa and the counts) and
writes `evals/results/calibration.json`. From then on `python -m evals run` and the report show the
agreement beside the judge's scores and drop `[UNCALIBRATED]`.

Labels file (version 1; ticket #106 saves labels in this format):

```json
{
  "version": 1,
  "run": "tuning-20260101-120000",
  "items": [
    {
      "id": "citation-01#0",
      "case_id": "citation-01",
      "question": "What does Súmula 7 say?",
      "expected_outcome": "States the thesis and cites the Precedent",
      "context": "[get_precedent] TESE: ...",
      "answer": "A tese é ...",
      "correctness": "correct",
      "grounding": "grounded"
    }
  ]
}
```

How to label: read `question`, `expected_outcome` and `context`, then the `answer`. Set
`correctness` to `correct` (does what the expected outcome asks), `incorrect` (wrong or beside the
point) or `refusal` (declines). Set `grounding` to `grounded` (every claim is in `context`),
`misgrounded` (relies on a result that does not support the claim) or `ungrounded` (states facts in
no result). Either field may be `unknown` when you cannot decide. Leave both empty to skip an item;
unlabeled items are ignored and counted. `id` is `<case_id>#<n>`, the n-th answer to that case in
the run; do not edit it. An invalid label makes `score` stop with an error and write nothing.

The record keeps `measured`, the run, the calibration model, the counts, the agreement and kappa per
axis (`correctness`, `grounding`), the `joint` agreement and every (human, judge) pair.

### Repetitions, consistency and the report

`python -m evals run` runs each Eval case `--repetitions N` times (default 3), each run kept as
its own Trajectory (`Trajectory.repetition`). Every `case#repetition` unit goes through
`Progress` (`evals/results/progress-<split>.json`): if the keys run out (`AllKeysExhausted`) or
the request cap is reached, the run stops with `Run stopped: ...` and exit code 1, the finished
units stay saved, and running the same command again resumes (after midnight Pacific time for a
daily quota). `--fresh` discards saved progress; a finished run clears it.

A run *passes* when its `tool_use` Score is 1.00. The Eval case declares its kind in the
`expected_state` field (assayer's loader has no tags field and accepts this one):

```json
{"id": "...", "input": "...", "expected_state": {"kind": "search"}}
```

* `lookup` (by CNJ number or id): **all-pass**, every run must pass.
* `search` (an open query): **at-least-one**, one passing run is enough.
* Unspecified means `lookup`: the strict rule is the default, so a missing declaration cannot
  hide an inconsistent agent. Any other value is an error.

The report prints the Experiment, then **Consistency** (passing runs and PASS/FAIL per case),
**Efficiency** (mean tool calls, tokens and tool errors per run, per case), and **Limits**.
A tool that failed twice or more with the same arguments inside a case is flagged `FLAG`: the
model tried the same thing again, which points at a tool description that does not say how to
call it (a failure naming `source_unavailable` is a Source, not arguments, and is not counted).
The limits state that name redaction is NER-based and best effort, that the agent is a small model whose scores
do not transfer to a stronger one, how many cassette misses occurred, and, when the agent and
judge model names share a family prefix (`gemini-...`), that the judge may favour the agent.
Sections are plain functions in `evals.report.SECTIONS`; a new metric appends its own.

The Experiment is saved to `evals/results/<split>-<YYYYmmdd-HHMMSS>.json` (git-ignored) with
its meta (split, repetitions, models). Compare two saved runs, the second minus the first:

```bash
uv run --group evals python -m evals compare seed-20261022-093005 seed-20261022-101500
```

Names resolve under `evals/results/`, or give a path. It prints the delta of each metric's mean
Score, of tokens and tool calls per Eval case (only cases both runs have) and of the share of
cases that pass by their rule, using assayer's `compare` for metrics and tokens.

### Citation existence Score

`citation_existence` reads the final answer for CNJ numbers (with or without punctuation) and
Precedent identifiers (`Tema 1002`, `Súmula 331`, `IRDR 12`, `RG 1002`) and checks that each one
appears in the output of a tool call of the same Trajectory (a failed call is not a source). Both
sides are normalised: a CNJ number to its 20 digits, a Precedent to kind sigla and number, so an
unpunctuated number in the answer matches a punctuated one in the results, and `Tema 1.002`
matches the id `stf-rg-1002`. The issuing body is not compared, and `Tema` matches `RG`, `RR`
or `IRR`; `Súmula Vinculante` is only `SV`.

The Score is the share of distinct citations found in the results (1.0 when all are). A citation
absent from them is named in the Score's comment (`fabricated citation: CNJ ...`), and the report
shows it on the case line. An answer with no citation is **not applicable** (no Score, no
failure), like `tool_use` for a case that expects no tool call. It only informs; nothing is
blocked. Citations are found by pattern, so a kind written in a form the patterns do not know
(`PN`, `CT`, a name in full) is not checked.

### Model client

The agent and the judge reach the model through `evals.llm.LLMClient`, a narrow Protocol
(`chat(messages, tools, system=) -> ChatResult` with text, tool calls and token usage). It is
injected, so tests use `ScriptedLLMClient` and never the Gemini API. `GeminiClient` is the only
implementation, over the REST API with httpx.

Configuration is read from the environment or `.env` (see `.env.example`): the agent, judge and
calibration model names, `EVALS_REQUESTS_PER_MINUTE`, `EVALS_TOKENS_PER_MINUTE`,
`EVALS_REQUESTS_PER_DAY`, `EVALS_MAX_REQUESTS_PER_RUN` and `GEMINI_API_KEY`. Copy the limits
from the AI Studio rate-limit page of your project; they are per project and per model
([research](../docs/research/gemini-free-tier-rate-limits.md)).

* Before each request the client waits so neither requests nor tokens per minute are exceeded
  (a one-minute sliding window; tokens are estimated, then corrected with the real usage).
* A 429 (or 503) is retried with exponential backoff, since no retry header is documented
  (`EVALS_MAX_RETRIES`, `EVALS_BACKOFF_BASE_SECONDS`, `EVALS_BACKOFF_MAX_SECONDS`).
* Every attempt counts toward the run cap, `min(EVALS_MAX_REQUESTS_PER_RUN,
  EVALS_REQUESTS_PER_DAY)`; past it the client raises `RequestCapReached`.
* The key travels in a header and is never in a log, error, `repr` or result; calls are
  identified by a key alias (`ChatResult.key_alias`).

### Key rotation and resuming a run

Rotation is **off by default**: with `GEMINI_API_KEY` alone, or with rotation off, the first key
is used exactly as before. To opt in, set `EVALS_ROTATE_KEYS=true` and give two or more keys in
`GEMINI_API_KEYS` (comma-separated). `key_source_from(settings)` builds the right `KeySource`.

* **Quotas are per project, not per key.** Rotation helps only across keys that belong to
  **different** Google projects; several keys of one project share one quota and gain nothing.
* A 429 is treated as daily-quota exhaustion when its body names a per-day quota (`...PerDay...`,
  "per day" or "daily"); the key is then skipped for the rest of the run and the call moves to the
  next key at once, without waiting or spending a retry. This is an **assumption**: the docs map
  429 to `quota_exceeded` (daily) and `rate_limit_exceeded` (per minute) but do not publish the
  body shape ([research](../docs/research/gemini-free-tier-rate-limits.md)). Any other 429 is a
  per-minute limit and is retried with backoff on the same key.
* When every key is exhausted the client raises `AllKeysExhausted`. The runner stops there; the
  daily quota resets at midnight Pacific time, so resume after that.
* Aliases are `key-1`, `key-2`, ... by position. Only the alias is recorded, never the key.

`evals.progress.Progress` is the resumable store the runner wraps around each unit of work:

```python
progress = Progress(Path("evals/results/progress-tuning.json"))  # git-ignored
try:
    for case in cases:
        for repetition in range(3):
            output = progress.run(unit_key(case.id, repetition), lambda: run_agent(case))
except AllKeysExhausted:
    ...  # progress is already saved; run the same command again after the quota resets
```

`run(key, work)` returns the stored output for a finished unit and otherwise calls `work`, saves
its JSON-serializable output (atomically, after every unit) and returns it. A unit that raises is
not recorded, so a resumed run repeats only the unfinished calls. Also available: `is_done`,
`get`, `record`, `clear` and `len`.

**Risk.** Using several keys to widen a free quota is the maintainer's own risk: Google's wider
terms of service were not read for this feature, and may restrict it.

### Redaction of personal data

`evals.redaction.Redactor().redact(value)` takes Source text (or a JSON-like structure of
it) and returns the same shape with personal data replaced, before a response is stored or
sent to a model. `redact(value)` is the one-off shortcut (a fresh `Redactor` per call). Record
mode uses one `Redactor` per Cassette, so the numbering is shared by all its responses.

* **CPF and CNPJ** become `[CPF]` and `[CNPJ]`, by their fixed patterns, with or without
  punctuation; no digit is kept. An unpunctuated run of 11 or 14 digits is taken as one, so an
  unrelated number of that length is replaced too.
* **Names of people** are found by **named-entity recognition** (spaCy, Portuguese model
  `pt_core_news_md`; only `PER` entities, `ORG`, `LOC` and `MISC` are left alone) and become
  `[PESSOA 1]`, `[PESSOA 2]`... The same person gets the same number across the Cassette:
  names are compared without case, accents, extra whitespace or connectors (`João da Silva` =
  `JOAO  SILVA`), and a name with two or more words that starts and ends like another and is
  contained in it in order (`João Silva`, `João Carlos Silva`) is the same person. Two people
  who share only a surname, or a name that fits more than one known person, count as different.
  A single word (`Joana`) matches only the same word. Runs of shouted words are shown to the model
  in title case, because it reads names in capitals poorly. Titles (`Dr.`, `Ministro`) stay.
* **Fallback patterns** back the model up where it misses an obvious name: a name after a party
  role (`autor`, `réu`, `advogado`...), after `Dr.`/`Sra.`, and an upper-case name right before
  `([OAB])`, `(CPF: ...)` or a role in parentheses.
* **Structured DJEN fields:** `nome` of a party (object with `polo`) or a lawyer (with
  `numero_oab`) is numbered like the names in the text, and `numero_oab` becomes `[OAB]`, by
  key; OAB registrations in text (`SP405006`, `OAB/SP 123`) become `[OAB]`.
* **Never touched:** CNJ numbers, Court aliases (`TJSP`, `TRF3`...) and Precedent kind
  siglas (`SUM`, `SV`, `RG`, `RR`, `IRDR`, `IAC`, `OJ`...), so the citation check still
  has something to compare. Legal terms (`Código de Defesa do Consumidor`, `Mérito Julgado`)
  and institutions are not names.

The model is the `evals` dependency group only (a pinned wheel, installed by `uv sync --group
evals`); the default `uv run --dev pytest` and CI do not need it. It loads in under a second.

Redaction is **best effort, not a guarantee**. What it misses (names that stay in the text):

* names the model does not tag: rare or foreign names, a single first name, initials
  (`J. da Silva`), names in lower case, and names inside a long upper-case block;
* a name inside a larger entity the model reads as one thing (`Apelação de João Silva`
  may stay whole if tagged `MISC`);
* people referred to by position or kinship (`o genitor`, `a síndica`).

It also gets things wrong the other way: a street, a company or a legal expression the model
tags as `PER` becomes `[PESSOA N]`, and two different people with the same name are one number
(and one person written in two unrelated ways is two). The numbers say "the same name", not
"the same human". Words that name an institution or a role (`Tribunal`, `Ministro`...) cut a
name, so `Maria Justiça Lima` is only partly replaced.

To apply a newer redaction to Cassettes already saved, offline:

```bash
uv run --group evals python -m evals.redact_cassettes [--check] [file ...]
```

It takes `cassettes/draft-*.json` by default, renumbers the people of each Cassette with a fresh
`Redactor`, keeps the recording date, and with `--check` writes nothing and exits 1 if anything
would change. A `[NOME]` left by the earlier heuristic redaction stays as it is: the name is gone
and cannot be numbered, so only a new recording gives `[PESSOA N]` there.

### Recording Cassettes

Record mode is off by default and never runs in tests (they use a scripted upstream). To
record the Cassette of an Eval case from the live DJEN, BNP and other Sources, opt in with
`JURIS_BRIDGE_EVALS_RECORD=1` (same style as `JURIS_BRIDGE_LIVE_BNP`):

```python
from evals.record import record_case

async def run(client):
    await client.call_tool("search_publications", {"court": "tjsp", ...})

path = await record_case("my-case-id", run)   # evals/cassettes/my-case-id.json
```

Without the variable `recording_session` / `record_case` raise `RecordingDisabledError` before
any transport exists, so no live request is possible. `run` gets an MCP client on the real
server; the recording transport sits under it (as the replay one does), keys requests with
`request_key`, redacts each response with one `Redactor` per Cassette (JSON bodies keep keys and structure; only
string values change), keeps only the `content-type` header and writes a Cassette dated with
the day of recording. A run that raises saves nothing. Replay it with `replay_session`.

Responsible use ([RESPONSIBLE_USE.md](../RESPONSIBLE_USE.md)):

* Recording is read-only: it forwards only what the server's read tools request.
* Requests are spaced at least `min_interval` seconds apart (default 1 s, under DataJud's 120
  per minute; the BNP and DJEN limits are undocumented), on top of the server's own limiter.
  Keep the number of cases and calls low.
* Redaction of names is best effort (NER misses and false positives): read a new Cassette before committing it. The request key
  is stored verbatim, so never record a query containing personal data.
* Do not redistribute DataJud-derived Cassettes outside your own non-commercial use.

### Draft Publication Eval cases

```bash
JURIS_BRIDGE_EVALS_RECORD=1 uv run --group evals python -m evals.draft_publications
```

Records, from the live DJEN, one Cassette per draft (`evals/cassettes/draft-pub-*.json`) and writes
`evals/cases/drafts/publications.json`. Searches by Court, text and a three-day window come first;
the CNJ numbers of the lookups (`kind: lookup`) are then taken from those recorded responses, never
from memory. Each draft's `reference_context_ids` and `expected_outcome` facts (counts, dates,
document types) are copied from the recorded response, and nothing about parties or text is
written. A Cassette that already exists is replayed instead of re-recorded, so a second run makes
no live request for it; delete it to refresh. Requests are 2 s apart, and the first Source
failure stops the run without retrying. Drafts count toward no result until you validate them.
`evals/tests/test_draft_publications.py` loads every draft and replays its first expected call
against its Cassette. Cassettes are large (a DJEN page is up to 100 full texts, about 8 MB for the
19); read them before committing.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Roadmap

See the tickets of the [spec (#90)](https://github.com/emvalencaf/juris-bridge-mcp/issues/90).

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Contributing

Follow [CONTRIBUTING.md](../CONTRIBUTING.md) and [CODE_STANDARDS.md](../CODE_STANDARDS.md).

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## License

Distributed under the Apache-2.0 licence. See [LICENSE](../LICENSE).

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Contact

Edson Mota Valença Filho - [@emvalencaf](https://github.com/emvalencaf)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Acknowledgments

* [Best-README-Template](https://github.com/othneildrew/Best-README-Template)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Draft Precedent, negative and Coverage cases

```bash
JURIS_BRIDGE_EVALS_RECORD=1 uv run --group evals python -m evals.draft_precedents [case-id ...]
```

Records 20 drafts into `cases/drafts/precedents.json` with their Cassettes. It is read-only and
paced (2 s between requests, a few requests per case); it stops at the first `source_unavailable`
and does not retry. Reference ids, status, thesis and the `not_covered` reason in
`expected_outcome` are copied from the recording, and a case whose recording does not show what
its spec claims (a negative that found something) is dropped with its Cassette. Name redaction
is NER-based and best effort; the drafts recorded before it (#100) still show `Código de [NOME]` or a
status as `[NOME]`, from the earlier heuristic. A thesis containing `[NOME]` is left out of the expected outcome. Drafts are unvalidated and
count toward no result; the maintainer reviews them before moving them to a split. Search drafts
(`kind: search`) take the top results of the day as references, which the BNP may reorder.
