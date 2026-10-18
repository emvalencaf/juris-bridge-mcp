<a id="readme-top"></a>


<br />
<div align="center">
  <h3 align="center">Juris Bridge MCP</h3>

  <p align="center">
    A remote, extensible and testable MCP server that gives AI agents access to Brazilian judicial data through a unified interface. Bridging AI Agents with Brazil's judicial ecosystem.
    <br />
    <a href="CONTRIBUTING.md"><strong>Explore the docs »</strong></a>
    <br />
    <br />
    <a href="https://github.com/emvalencaf/juris-bridge-mcp/issues/new">Report Bug</a>
    &middot;
    <a href="https://github.com/emvalencaf/juris-bridge-mcp/issues/new">Request Feature</a>
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

A remote, extensible and testable MCP server that gives AI agents access to Brazilian judicial data through a unified interface. Bridging AI Agents with Brazil's judicial ecosystem.


<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Built With

* [Python](https://www.python.org) managed with [uv](https://docs.astral.sh/uv/)
* [ruff](https://docs.astral.sh/ruff/)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Getting Started

### Prerequisites


* [`uv`](https://docs.astral.sh/uv/)

### Installation

1. Clone the repository
   ```bash
   git clone https://github.com/emvalencaf/juris-bridge-mcp.git
   cd juris-bridge-mcp
   ```
2. Enable the git hooks
   ```bash
   scripts/setup.sh
   ```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Usage

### Running the server

The same image runs everywhere; it only reads environment variables (see `.env.example`).

```bash
# uv
JURIS_BRIDGE_SERVER_API_KEYS=my-key JURIS_BRIDGE_DATAJUD_API_KEY=... uv run python -m juris_bridge_mcp.main

# container (MCP endpoint: http://localhost:8000/mcp, Authorization: Bearer my-key)
docker build -t juris-bridge-mcp .
docker run --rm -p 8000:8000 --env-file .env juris-bridge-mcp
```

The AWS Reference deployment (Lambda + Function URL, Terraform) lives in
[`deploy/aws/`](deploy/aws/README.md); run `deploy/aws/deploy.sh`.

### Known limits

- The rate limiter is **per instance**: each warm environment counts on its own, so
  several instances can together exceed a Source's limit (DataJud: 120 req/min).
- The in-memory cache is **per warm environment**: it is lost on cold start and
  not shared between instances.
- The `revoked` and `superseded` flags of a norm article rest on the Planalto markup (a
  `(Revogado ...)` note, or a struck-through opening line). Older pages mark them
  inconsistently, so a revoked article can be missed or a current one flagged.
- An article runs to the next article or heading. A rubric the parser does not recognise as a
  title can still trail an article in older norms.
- Planalto page paths are built by convention, as there is no index by URN. Norms without a
  convention (a `mensagem`, old provisional measures) and some pre-2004 layouts return metadata
  and a warning, not the text, unless Câmara Legin has them.
- When the Planalto has no page or refuses, the text comes from Câmara Legin, whose URL is not
  derivable from the URN and is read off the LexML URN page and the Câmara data sheet. If the
  LexML portal serves its security challenge, the server does not solve it and the call is
  `source_blocked`. The Legin text carries few Annotations, its `warnings` give the amending
  norms from the data sheet as hints only, and a very large consolidated page (e.g. Lei
  14.133) may time out at the Câmara (`source_unavailable`, retryable).


<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Roadmap

- [ ] First milestone

See the [open issues](https://github.com/emvalencaf/juris-bridge-mcp/issues) for proposed features and known issues.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Contributing

Contributions follow the branch strategy and commit convention in
[CONTRIBUTING.md](CONTRIBUTING.md): cut a branch from `development`, commit as
`tag(subject/subsubject): summary`, and open a pull request into `development`.
Coding and documentation rules are in [CODE_STANDARDS.md](CODE_STANDARDS.md).

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## License

No license has been chosen yet.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Contact

Edson Mota Valença Filho - [@emvalencaf](https://github.com/emvalencaf)

Project Link: [https://github.com/emvalencaf/juris-bridge-mcp](https://github.com/emvalencaf/juris-bridge-mcp)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Acknowledgments

* [Best-README-Template](https://github.com/othneildrew/Best-README-Template)

<p align="right">(<a href="#readme-top">back to top</a>)</p>
