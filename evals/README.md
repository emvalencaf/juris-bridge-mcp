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

At this stage only the skeleton exists: the command below loads an empty Dataset
and prints an empty Experiment, which proves the wiring. The agent loop, the
Cassettes and the metrics arrive in later tickets of the spec.

| Path | Holds |
|---|---|
| `__main__.py` | The command (`python -m evals`) |
| `dataset.py` | Loads Eval cases from the split folders |
| `redaction.py` | `redact()`: replaces personal data in Source text with placeholders |
| `cassette.py` | The Cassette format and the transport that replays it in place of the network; a request with no recording is a counted miss answered as `source_unavailable` |
| `cassettes/` | One `<case id>.json` Cassette per Eval case, with its recording date |
| `cases/tuning/`, `cases/validation/`, `cases/drafts/` | Eval cases as plain JSON lists, split by folder; drafts count toward no result |
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
uv run --group evals python -m evals
```

It prints an Experiment with no cases, trajectories, scores or failures. To run
the tests of the evaluation itself (the default `pytest` run skips them):

```bash
uv run --group evals pytest evals
```

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
  identified by a key alias. Key rotation and resuming a stopped run are a later ticket (#96);
  `KeySource` is the seam for it.

### Redaction of personal data

`evals.redaction.redact(value)` takes Source text (or a JSON-like structure of it) and
returns the same shape with personal data replaced, before a response is stored or sent
to a model.

* **CPF and CNPJ** become `[CPF]` and `[CNPJ]`, by their fixed patterns, with or without
  punctuation. An unpunctuated run of 11 or 14 digits is taken as one, so an unrelated
  number of that length is replaced too.
* **Names of people** become `[NOME]` by **heuristics only, not a guarantee**: a name
  after a party role (`autor`, `réu`, `requerente`, `advogado`...), and runs of two or
  more capitalised words. Institutional words (`Tribunal`, `Justiça`, `Ministério`...)
  split a run and are kept.
* **Never touched:** CNJ numbers, Court aliases (`TJSP`, `TRF3`...) and Precedent kind
  siglas (`SUM`, `SV`, `RG`, `RR`, `IRDR`, `IAC`, `OJ`...), so the citation check still
  has something to compare.

What the name redaction misses (names that stay in the text):

* a single-word name outside a role (`Joana`), nicknames and initials (`J. da Silva`);
* names written in lower case or all caps outside a role;
* a name after a role not in the list, or a second party after the first one's name
  (`Réu: João Silva, Maria Souza`: only the first is certain);
* names that contain an institutional word (`Maria Justiça Lima` is split);
* people referred to by position or kinship (`o genitor`, `a síndica`).

It also over-redacts: a capitalised run that is not a person (a street, a company, a
place such as `Praça Tiradentes`, a sentence start followed by a proper noun) becomes
`[NOME]`, and runs of whitespace inside a redacted run collapse to one space.

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
