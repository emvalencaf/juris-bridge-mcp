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
| `cassette.py` | The Cassette format and the transport that replays it in place of the network; a request with no recording is a counted miss answered as `source_unavailable` |
| `cassettes/` | One `<case id>.json` Cassette per Eval case, with its recording date |
| `cases/tuning/`, `cases/validation/`, `cases/drafts/` | Eval cases as plain JSON lists, split by folder; drafts count toward no result |
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
