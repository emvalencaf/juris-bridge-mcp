"""Cassettes: dated, recorded Source responses replayed in place of the network.

A Cassette is one JSON file per Eval case, `evals/cassettes/<case id>.json`:

    {
      "recorded_on": "2026-10-22",
      "entries": [
        {"key": "GET https://host/path?a=1&b=2", "status": 200,
         "headers": {"content-type": "application/json"},
         "body": "<utf-8 text>"}            # or "body_base64" when not valid UTF-8
      ]
    }

Entries are matched by `request_key`: method, URL with its query sorted, and a short digest
of the body when there is one. Headers never take part (they carry credentials and
user-agents). The record mode (#94) writes the same format and must key with `request_key`.

`ReplayTransport` is the seam the Sources already take (`transport=` of `build_server`).
A request with no entry never touches the network: it is answered `503` with a huge
`Retry-After`, so the real `UpstreamClient` gives up at once and the real adapters surface
the `source_unavailable` Error code, and it is counted as a cassette miss.
"""

import base64
import hashlib
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx
from fastmcp import Client, FastMCP
from pydantic import SecretStr

from juris_bridge_mcp.config.bnp import BnpSettings
from juris_bridge_mcp.config.datajud import DatajudSettings
from juris_bridge_mcp.config.djen import DjenSettings
from juris_bridge_mcp.config.http import HttpSettings
from juris_bridge_mcp.config.legin import LeginSettings
from juris_bridge_mcp.config.planalto import PlanaltoSettings
from juris_bridge_mcp.config.senado import SenadoSettings
from juris_bridge_mcp.infrastructure.bootstrap import build_server

CASSETTES_DIR = Path(__file__).parent / "cassettes"

# Longer than any wait the server tolerates, so a miss is not retried.
_MISS_RETRY_AFTER_SECONDS = "86400"


def request_key(request: httpx.Request) -> str:
    """Identify a request: `METHOD url?sorted-query` plus `#<digest>` of a non-empty body."""
    url = request.url
    query = urlencode(sorted(url.params.multi_items()))
    key = f"{request.method} {url.copy_with(query=None, fragment=None)}"
    if query:
        key += f"?{query}"
    if request.content:
        key += f"#{hashlib.sha256(request.content).hexdigest()[:16]}"
    return key


@dataclass(frozen=True)
class CassetteEntry:
    """One recorded response."""

    key: str
    status: int
    headers: dict[str, str]
    body: bytes

    @classmethod
    def from_response(
        cls, key: str, status: int, headers: dict[str, str], body: bytes
    ) -> "CassetteEntry":
        """Build an entry from the parts of a response."""
        return cls(key=key, status=status, headers=dict(headers), body=body)

    def to_json(self) -> dict[str, Any]:
        """Return the JSON form: text `body` when UTF-8, else `body_base64`."""
        data: dict[str, Any] = {"key": self.key, "status": self.status, "headers": self.headers}
        try:
            data["body"] = self.body.decode("utf-8")
        except UnicodeDecodeError:
            data["body_base64"] = base64.b64encode(self.body).decode("ascii")
        return data

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "CassetteEntry":
        """Read an entry from its JSON form."""
        if "body_base64" in data:
            body = base64.b64decode(data["body_base64"])
        else:
            body = data["body"].encode("utf-8")
        return cls(data["key"], data["status"], data.get("headers", {}), body)

    def to_response(self) -> httpx.Response:
        """Build the httpx response this entry replays."""
        return httpx.Response(self.status, headers=self.headers, content=self.body)


@dataclass
class Cassette:
    """The recorded responses of one Eval case and the date they were recorded."""

    recorded_on: date
    entries: dict[str, CassetteEntry] = field(default_factory=dict)

    def save(self, path: Path) -> None:
        """Write the Cassette as JSON, creating the folder."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "recorded_on": self.recorded_on.isoformat(),
            "entries": [entry.to_json() for entry in self.entries.values()],
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Cassette":
        """Read a Cassette written by `save`."""
        data = json.loads(path.read_text(encoding="utf-8"))
        entries = [CassetteEntry.from_json(e) for e in data["entries"]]
        return cls(date.fromisoformat(data["recorded_on"]), {e.key: e for e in entries})


def cassette_path(case_id: str, *, root: Path = CASSETTES_DIR) -> Path:
    """Return where the Cassette of an Eval case lives."""
    return root / f"{case_id}.json"


class ReplayTransport(httpx.AsyncBaseTransport):
    """Serve a Cassette; count and refuse (as `source_unavailable`) what it lacks."""

    def __init__(self, cassette: Cassette) -> None:
        self.cassette = cassette
        self.missed: list[str] = []

    @property
    def misses(self) -> int:
        """How many requests had no recording."""
        return len(self.missed)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Answer from the Cassette, or with the miss response."""
        key = request_key(request)
        entry = self.cassette.entries.get(key)
        if entry is not None:
            return entry.to_response()
        self.missed.append(key)
        return httpx.Response(
            503,
            headers={"Retry-After": _MISS_RETRY_AFTER_SECONDS},
            content=b"cassette miss",
        )


@dataclass
class ReplaySession:
    """An in-memory MCP client over the real server, fed by a Cassette."""

    client: Client[Any]
    transport: ReplayTransport

    @property
    def cassette(self) -> Cassette:
        """The Cassette being replayed."""
        return self.transport.cassette

    @property
    def misses(self) -> int:
        """The cassette-miss count so far."""
        return self.transport.misses


def build_eval_server(transport: httpx.AsyncBaseTransport) -> FastMCP[Any]:
    """Build the real server with every Source reached through `transport`."""
    return build_server(
        datajud=DatajudSettings(api_key=SecretStr("replay-key")),
        djen=DjenSettings(),
        bnp=BnpSettings(),
        http=HttpSettings(),
        senado=SenadoSettings(),
        planalto=PlanaltoSettings(),
        legin=LeginSettings(),
        transport=transport,
    )


@asynccontextmanager
async def replay_session(cassette: Cassette) -> AsyncIterator[ReplaySession]:
    """Build the real server over `cassette` and yield a connected in-memory client."""
    transport = ReplayTransport(cassette)
    async with Client(build_eval_server(transport)) as client:
        yield ReplaySession(client, transport)
