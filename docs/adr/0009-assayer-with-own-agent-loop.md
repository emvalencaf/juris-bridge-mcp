# Evaluate the server with assayer and our own agent loop

The server is evaluated by putting questions to an agent connected to it and scoring
what the agent did (see the spec, issue #90, and
`docs/research/mcp-evaluation-practices.md`). The scoring uses `assayer`, the
maintainer's own library (`llm-assayer-eval`), and the agent is a loop of a few dozen
lines that we write: it sends the question and the tool list to a Gemini model, runs
the tool calls against the real server and feeds the results back until the model
answers. assayer lives in a development-only dependency group and the evaluation in a
top-level `evals/` directory, so neither the published package nor the default test
run and CI depend on it.

## Considered

- **Inspect AI:** the most complete framework, with MCP tool support, model-graded
  scorers and epoch reducers. It treats MCP as a way to give an agent tools, not as a
  server under test, and brings no golden-set retrieval score or citation check, so
  we would write those scorers anyway inside a larger framework.
- **promptfoo:** can call MCP tools directly and assert on the results, and its
  red-team plugins exist, but it is driven by YAML and JavaScript assertions and has
  no ready retrieval or citation scoring. Our scores would live in another language.
- **DeepEval:** has a first-class MCP model and an `MCPUseMetric`, but the metric is a
  model judgement of the tools chosen and not a deterministic check, and it too lacks
  retrieval against a golden set and citation existence.

## Consequences

The one thing a framework would save is the agent loop, and writing it ourselves keeps
control of the rate limits, the key rotation and the Cassette transport, which the free
Gemini quotas make necessary. assayer already provides tool correctness, retrieval
precision and recall, faithfulness judging, consistency and token tracking, and the
citation check is a small custom metric. The cost is that we own and maintain the loop
and that assayer is young and has one maintainer; if that becomes a problem, the Eval
cases are plain JSON and the loop is small enough to move to another framework.

## Note: names are redacted with a named-entity model

The first redaction of names (#92) was a set of patterns. It over-redacted legal terms and
could not tell whether two names were one person, so the maintainer asked for named-entity
recognition: spaCy with `pt_core_news_md`, which, like assayer, lives only in the `evals`
dependency group (the model is a pinned wheel in `pyproject.toml`). The default test run and CI
do not install it. Redaction stays best effort.

The tests of `evals/` run only with `uv run --group evals pytest evals`. They are not
part of `uv run pytest` or CI, and `evals/` is outside the published package.
