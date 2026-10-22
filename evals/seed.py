"""The seed Cassettes: hand-made from the repository's Source fixtures, not recorded.

They exist so the first end-to-end slice runs offline before any live recording (#94). They
are not real recordings: the responses are the fictitious DJEN and BNP fixtures the
contract tests already use, and `recorded_on` is the day they were built. Regenerate them
with `uv run --group evals python -m evals.seed`.

The requests a seed Cassette answers are those of the plausible calls to the tools an
Eval case expects, learnt by running the real tools through a transport that serves the
fixture of the Source being asked. A call the Cassette does not cover is a cassette miss.
"""

import asyncio
import sys
from datetime import date
from pathlib import Path
from typing import Any

import httpx
from fastmcp import Client
from pydantic import SecretStr

from evals.cassette import (
    CASSETTES_DIR,
    Cassette,
    CassetteEntry,
    cassette_path,
    request_key,
)
from juris_bridge_mcp.config.bnp import BnpSettings
from juris_bridge_mcp.config.datajud import DatajudSettings
from juris_bridge_mcp.config.djen import DjenSettings
from juris_bridge_mcp.config.http import HttpSettings
from juris_bridge_mcp.config.legin import LeginSettings
from juris_bridge_mcp.config.planalto import PlanaltoSettings
from juris_bridge_mcp.config.senado import SenadoSettings
from juris_bridge_mcp.infrastructure.bootstrap import build_server

FIXTURES = Path(__file__).parents[1] / "tests/contract/providers"
DJEN_FIXTURE = FIXTURES / "djen/fixtures/tjsp_decisions.json"
BNP_FIXTURE = FIXTURES / "bnp/fixtures/stf_rg_1002.json"
CNJ = "1234567-76.2025.8.26.0100"

# Eval case id -> the (tool, arguments) calls whose requests the Cassette must answer.
SEED_CALLS: dict[str, list[tuple[str, dict[str, Any]]]] = {
    "seed-publications-by-cnj": [
        (
            "search_publications",
            {"cnj_number": CNJ, "date_from": "2026-10-15", "date_to": "2026-10-15"},
        ),
        (
            "search_publications",
            {
                "cnj_number": CNJ,
                "court": "tjsp",
                "date_from": "2026-10-15",
                "date_to": "2026-10-15",
            },
        ),
    ],
    "seed-precedent-rg-1002": [
        ("search_precedents", {"number": "1002", "kind": "RG", "court": "stf"}),
        ("search_precedents", {"number": "1002", "kind": "RG"}),
        ("search_precedents", {"number": "1002", "court": "stf"}),
        ("search_precedents", {"number": "1002"}),
        ("search_precedents", {"query": "tema 1002", "court": "stf"}),
        ("search_precedents", {"query": "tema 1002"}),
        ("get_precedent", {"id": "stf-rg-1002"}),
    ],
    "seed-coverage": [("list_coverage", {})],
}


class _FixtureTransport(httpx.AsyncBaseTransport):
    """Answer each request with the fixture of the Source it is addressed to, and keep it."""

    def __init__(self) -> None:
        self.entries: dict[str, CassetteEntry] = {}

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.url.host == httpx.URL(DjenSettings().base_url).host:
            body = DJEN_FIXTURE.read_bytes()
        elif request.url.host == httpx.URL(BnpSettings().base_url).host:
            body = BNP_FIXTURE.read_bytes()
        else:
            return httpx.Response(503, content=b"no fixture")
        key = request_key(request)
        headers = {"content-type": "application/json"}
        self.entries[key] = CassetteEntry.from_response(key, 200, headers, body)
        return httpx.Response(200, headers=headers, content=body)


async def build_seed_cassette(calls: list[tuple[str, dict[str, Any]]], day: date) -> Cassette:
    """Run `calls` through the real server over fixtures and return what it requested."""
    transport = _FixtureTransport()
    server = build_server(
        datajud=DatajudSettings(api_key=SecretStr("seed-key")),
        djen=DjenSettings(),
        bnp=BnpSettings(),
        http=HttpSettings(),
        senado=SenadoSettings(),
        planalto=PlanaltoSettings(),
        legin=LeginSettings(),
        transport=transport,
    )
    async with Client(server) as client:
        for name, arguments in calls:
            await client.call_tool(name, arguments, raise_on_error=False)
    return Cassette(recorded_on=day, entries=transport.entries)


async def write_seed_cassettes(root: Path = CASSETTES_DIR, day: date | None = None) -> list[Path]:
    """Write one seed Cassette per seed Eval case under `root`."""
    day = day or date.today()
    written = []
    for case_id, calls in SEED_CALLS.items():
        cassette = await build_seed_cassette(calls, day)
        path = cassette_path(case_id, root=root)
        cassette.save(path)
        written.append(path)
    return written


if __name__ == "__main__":
    for written_path in asyncio.run(write_seed_cassettes()):
        print(written_path)
    sys.exit(0)
