"""Extend recorded Cassettes with the requests an agent made that they had no answer for.

Run by hand, opt-in, read-only and paced (see `evals.record`):

    JURIS_BRIDGE_EVALS_RECORD=1 uv run --group evals python -m evals.extend_cassettes

A Cassette answers only the exact request it recorded, so an agent that words a search another
way, or opens a Publication it just found, gets a cassette miss. This command reads the latest
saved run of each split (`evals/results/`), takes the tool calls that ended in
`source_unavailable` for an Eval case, adds a `get_publication` of the first Publication of
each lookup case, and records those calls from the live Sources into the case's Cassette.
Entries already recorded are kept and served from the Cassette, so they cost no request; the
new ones are redacted like any other recording. A call that fails live stops the run without
retrying.
"""

import asyncio
import json
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import httpx

from evals.cassette import Cassette, ReplayTransport, cassette_path, replay_session
from evals.dataset import load_split
from evals.record import RecordOptions, recording_session

RESULTS_DIR = Path(__file__).parent / "results"
MIN_INTERVAL_SECONDS = 2.0
VALIDATED_SPLITS = ("tuning", "validation")

Call = tuple[str, dict[str, Any]]


def missed_calls(results_dir: Path = RESULTS_DIR) -> dict[str, list[Call]]:
    """The tool calls of the latest saved run of each split that found no recording, per case."""
    found: dict[str, list[Call]] = {}
    latest = {path.name.split("-")[0]: path for path in sorted(results_dir.glob("*.json"))}
    for path in latest.values():
        experiment = json.loads(path.read_text(encoding="utf-8")).get("experiment", {})
        for trajectory in experiment.get("trajectories", []):
            for step in trajectory["steps"]:
                if step.get("kind") != "tool" or "source_unavailable" not in (
                    step.get("error") or ""
                ):
                    continue
                call = (step["name"], step["input"])
                calls = found.setdefault(trajectory["case_id"], [])
                if call not in calls:
                    calls.append(call)
    return found


async def _first_publication_id(case_id: str, call: Call) -> str | None:
    """The id of the first Publication the case's own first call returns, from its Cassette."""
    async with replay_session(Cassette.load(cassette_path(case_id))) as session:
        result = await session.client.call_tool(call[0], call[1], raise_on_error=False)
    items = (result.structured_content or {}).get("items") or []
    return items[0]["id"] if items else None


class _Layered(httpx.AsyncBaseTransport):
    """Serve what the Cassette holds; send the rest to the live Source."""

    def __init__(self, cassette: Cassette) -> None:
        self.replay = ReplayTransport(cassette)
        self.live = httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        from evals.cassette import request_key

        if request_key(request) in self.replay.cassette.entries:
            return await self.replay.handle_async_request(request)
        return await self.live.handle_async_request(request)


async def extend(case_id: str, calls: Iterable[Call]) -> int:
    """Record `calls` into the Cassette of `case_id`; return how many entries it gained."""
    path = cassette_path(case_id)
    existing = Cassette.load(path)
    options = RecordOptions(inner=_Layered(existing), min_interval=MIN_INTERVAL_SECONDS)
    async with recording_session(case_id, options) as (client, recorded):
        for name, arguments in calls:
            result = await client.call_tool(name, arguments, raise_on_error=False)
            text = " ".join(getattr(b, "text", "") for b in result.content)
            if result.is_error and "source_unavailable" in text:
                raise RuntimeError(f"{case_id}: {name} {arguments}: {text[:120]}")
    gained = {k: v for k, v in recorded.entries.items() if k not in existing.entries}
    existing.entries.update(gained)
    existing.save(path)
    return len(gained)


async def main() -> int:
    """Extend the Cassettes of the validated cases; print what each gained."""
    wanted = set(sys.argv[1:])
    cases = {c.id: c for split in VALIDATED_SPLITS for c in load_split(split).cases}
    plan = missed_calls()
    for case_id, case in cases.items():
        if case_id.startswith("draft-pub-lookup-"):
            call = case.expected_tool_calls[0]
            identifier = await _first_publication_id(case_id, (call["name"], call["arguments"]))
            if identifier:
                plan.setdefault(case_id, []).append(("get_publication", {"id": identifier}))
    total = 0
    for case_id, calls in plan.items():
        if case_id not in cases or (wanted and case_id not in wanted):
            continue
        gained = await extend(case_id, calls)
        total += gained
        print(f"{case_id}: {len(calls)} call(s), {gained} new entr(y/ies)")
    print(
        f"{total} entries added; run the redaction check: python -m evals.redact_cassettes --check"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
