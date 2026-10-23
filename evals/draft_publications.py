"""Draft Publication Eval cases from Cassettes recorded on the live DJEN.

Run by hand, with the opt-in of record mode (read-only, paced, few requests per case):

    JURIS_BRIDGE_EVALS_RECORD=1 uv run --group evals python -m evals.draft_publications

Two steps, so that no CNJ number comes from memory:

1. *Search* drafts: each `SEARCH_SPECS` entry (a Court, a text and a short window) is recorded
   as one Cassette and drafted as a `search` Eval case.
2. *Lookup* drafts: CNJ numbers are taken from the recorded search responses (at most one per
   search, distinct, up to `LOOKUP_COUNT`), and each is recorded as its own Cassette and
   drafted as a `lookup` Eval case over the window of the search it came from.

Every expected value of a draft (tool arguments aside, which are the question's own) is copied
from the recorded response: the CNJ numbers for `reference_context_ids`, the counts, dates and
document types for `expected_outcome`. Nothing is written about parties or text. The drafts go to
`evals/cases/drafts/publications.json`, unvalidated, and count toward no result.

Stops at the first Source failure (`source_unavailable`, `rate_limited`, ...): the Source is
not retried, and what was already recorded is kept.
"""

import asyncio
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from fastmcp import Client

from evals.cassette import CASSETTES_DIR, Cassette, cassette_path, replay_session
from evals.record import RECORD_ENV, RecordingDisabledError, record_case, recording_enabled

DRAFTS_PATH = Path(__file__).parent / "cases" / "drafts" / "publications.json"

# Seconds between requests and between cases: gentle on a Source whose limits are undocumented.
MIN_INTERVAL_SECONDS = 2.0
PAUSE_BETWEEN_CASES_SECONDS = 3.0
SEARCH_LIMIT = 5
LOOKUP_COUNT = 10
WINDOW = (date(2026, 10, 19), date(2026, 10, 21))


@dataclass(frozen=True)
class SearchSpec:
    """One text search to record: `id` suffix, Court alias, text and window."""

    slug: str
    court: str
    query: str
    date_from: date = WINDOW[0]
    date_to: date = WINDOW[1]


SEARCH_SPECS: tuple[SearchSpec, ...] = (
    SearchSpec("tjsp-recurso", "tjsp", "recurso"),
    SearchSpec("tjsp-tutela", "tjsp", "tutela"),
    SearchSpec("tjmg-apelacao", "tjmg", "apelação"),
    SearchSpec("tjrj-sentenca", "tjrj", "sentença"),
    SearchSpec("tjrs-agravo", "tjrs", "agravo"),
    SearchSpec("tjpr-embargos", "tjpr", "embargos"),
    SearchSpec("trf1-previdenciario", "trf1", "previdenciário"),
    SearchSpec("trf3-aposentadoria", "trf3", "aposentadoria"),
    SearchSpec("trf4-contribuicao", "trf4", "contribuição"),
    SearchSpec("stj-especial", "stj", "especial"),
)


class SourceBlockedError(RuntimeError):
    """The live Source answered with an error; recording stops and does not retry."""


def search_id(spec: SearchSpec) -> str:
    """Return the Eval case id (and Cassette name) of a search draft."""
    return f"draft-pub-search-{spec.slug}"


def lookup_id(index: int, court: str) -> str:
    """Return the Eval case id (and Cassette name) of the `index`-th lookup draft."""
    return f"draft-pub-lookup-{index:02d}-{court}"


def _br(day: date | str) -> str:
    return date.fromisoformat(str(day)).strftime("%d/%m/%Y")


def _items(result: dict[str, Any]) -> list[dict[str, Any]]:
    return list(result.get("items", []))


def _facts(result: dict[str, Any]) -> str:
    """State, from the recorded response only, what it held (counts, dates, kinds)."""
    items = _items(result)
    days = sorted({str(i["published_on"]) for i in items})
    kinds = sorted({str(i["kind"]) for i in items})
    docs = sorted({str(i["document_type"]) for i in items})
    state = (
        "complete" if result.get("complete") else f"incomplete ({result.get('incomplete_reason')})"
    )
    return (
        f"The Source returned {len(items)} Publication(s) ({state}) released on "
        f"{', '.join(days)}; document types: {'; '.join(docs)}; kinds: {', '.join(kinds)}."
    )


def draft_search(spec: SearchSpec, result: dict[str, Any]) -> dict[str, Any]:
    """Build the draft Eval case of a recorded text search."""
    items = _items(result)
    cnjs = list(dict.fromkeys(str(i["cnj_number"]) for i in items))
    return {
        "id": search_id(spec),
        "input": (
            f'Procure no {spec.court.upper()} publicações com o termo "{spec.query}" '
            f"disponibilizadas entre {_br(spec.date_from)} e {_br(spec.date_to)}."
        ),
        "expected_tool_calls": [
            {
                "name": "search_publications",
                "arguments": {
                    "court": spec.court,
                    "query": spec.query,
                    "date_from": spec.date_from.isoformat(),
                    "date_to": spec.date_to.isoformat(),
                },
            }
        ],
        "reference_context_ids": cnjs,
        "expected_outcome": (
            f'Reports the Publications found in {spec.court.upper()} for "{spec.query}" between '
            f"{spec.date_from.isoformat()} and {spec.date_to.isoformat()}, citing only CNJ numbers "
            f"the tool returned. {_facts(result)}"
        ),
        "expected_state": {"kind": "search"},
    }


def draft_lookup(
    case_id: str, cnj: str, date_from: date, date_to: date, result: dict[str, Any]
) -> dict[str, Any]:
    """Build the draft Eval case of a recorded lookup by CNJ number."""
    items = _items(result)
    return {
        "id": case_id,
        "input": (
            f"Quais publicações há no processo {cnj} entre {_br(date_from)} e {_br(date_to)}?"
        ),
        "expected_tool_calls": [
            {
                "name": "search_publications",
                "arguments": {
                    "cnj_number": cnj,
                    "date_from": date_from.isoformat(),
                    "date_to": date_to.isoformat(),
                },
            }
        ],
        "reference_context_ids": list(dict.fromkeys(str(i["cnj_number"]) for i in items)) or [cnj],
        "expected_outcome": (
            f"Lists the Publications of Case {cnj} in the window, citing only CNJ numbers the "
            f"tool returned. {_facts(result)}"
        ),
        "expected_state": {"kind": "lookup"},
    }


def _structured(result: Any) -> dict[str, Any]:
    if result.is_error:
        text = result.content[0].text if result.content else "no detail"
        raise SourceBlockedError(text)
    data = result.structured_content
    if not isinstance(data, dict):
        raise SourceBlockedError("the tool answered without structured content")
    return data


async def _record_search(
    case_id: str, arguments: dict[str, Any], root: Path, **options: Any
) -> dict[str, Any]:
    captured: dict[str, Any] = {}
    existing = cassette_path(case_id, root=root)
    if existing.exists():  # already recorded: replay it, no live request
        async with replay_session(Cassette.load(existing)) as session:
            result = await session.client.call_tool(
                "search_publications", arguments, raise_on_error=False
            )
        return _structured(result)

    async def run(client: Client[Any]) -> None:
        result = await client.call_tool("search_publications", arguments, raise_on_error=False)
        captured.update(_structured(result))

    await record_case(case_id, run, root=root, min_interval=MIN_INTERVAL_SECONDS, **options)
    return captured


async def draft_all(
    specs: Sequence[SearchSpec] = SEARCH_SPECS,
    *,
    root: Path = CASSETTES_DIR,
    drafts_path: Path = DRAFTS_PATH,
    lookup_count: int = LOOKUP_COUNT,
    pause: float = PAUSE_BETWEEN_CASES_SECONDS,
    **options: Any,
) -> list[dict[str, Any]]:
    """Record the searches, then the lookups, and write the drafts; return them.

    Raises:
        RecordingDisabledError: `JURIS_BRIDGE_EVALS_RECORD` is not `1`.
        SourceBlockedError: the Source failed; the drafts of what was recorded are still written.
    """
    drafts: list[dict[str, Any]] = []
    candidates: list[tuple[str, SearchSpec]] = []
    blocked: SourceBlockedError | None = None
    try:
        for spec in specs:
            arguments = {
                "court": spec.court,
                "query": spec.query,
                "date_from": spec.date_from.isoformat(),
                "date_to": spec.date_to.isoformat(),
                "limit": SEARCH_LIMIT,
            }
            result = await _record_search(search_id(spec), arguments, root, **options)
            if _items(result):
                drafts.append(draft_search(spec, result))
                candidates.append((str(_items(result)[0]["cnj_number"]), spec))
            else:
                cassette_path(search_id(spec), root=root).unlink(missing_ok=True)
            await asyncio.sleep(pause)
        picked: list[tuple[str, SearchSpec]] = []
        for cnj, spec in candidates:
            if cnj not in {p[0] for p in picked}:
                picked.append((cnj, spec))
        for index, (cnj, spec) in enumerate(picked[:lookup_count], start=1):
            case_id = lookup_id(index, spec.court)
            arguments = {
                "cnj_number": cnj,
                "date_from": spec.date_from.isoformat(),
                "date_to": spec.date_to.isoformat(),
            }
            result = await _record_search(case_id, arguments, root, **options)
            if _items(result):
                drafts.append(draft_lookup(case_id, cnj, spec.date_from, spec.date_to, result))
            else:
                cassette_path(case_id, root=root).unlink(missing_ok=True)
            await asyncio.sleep(pause)
    except SourceBlockedError as error:
        blocked = error
    drafts_path.parent.mkdir(parents=True, exist_ok=True)
    drafts_path.write_text(
        json.dumps(drafts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if blocked is not None:
        raise blocked
    return drafts


def main() -> int:
    """Record and draft; exit 1 when recording is off or the Source failed."""
    if not recording_enabled():
        print(
            f"Set {RECORD_ENV}=1 to record from the live DJEN (read-only, paced).",
            file=sys.stderr,
        )
        return 1
    try:
        drafts = asyncio.run(draft_all())
    except RecordingDisabledError as error:
        print(error, file=sys.stderr)
        return 1
    except SourceBlockedError as error:
        print(f"Source failure, stopped without retrying: {error}", file=sys.stderr)
        return 1
    print(f"Wrote {len(drafts)} drafts to {DRAFTS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
