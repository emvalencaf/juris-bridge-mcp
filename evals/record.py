"""Record mode: capture live Source responses into a Cassette, redacted and paced.

Opt-in, in the style of the BNP live check: nothing is recorded unless
`JURIS_BRIDGE_EVALS_RECORD=1` is set. Without it a recording session is refused before any
transport is built, so no request can reach a live Source. The transport sits under the real
server (as `ReplayTransport` does) and uses the same `request_key` and Cassette format.

Responses are redacted before they are stored, all through one `Redactor` per Cassette so that a
person keeps one `[PESSOA N]` across its responses: for a JSON body only the string values
change, keys and structure are kept. Only the `content-type` header is kept.
The request key is stored as is, because replay matches on it; the server has no CPF, party or
judge search, so it carries no personal data. Requests are spaced at least `min_interval`
seconds apart on top of the server's own rate limiter. Recording is read-only: it only
forwards the requests the server's read tools make.
"""

import asyncio
import json
import os
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import httpx
from fastmcp import Client

from evals.cassette import (
    CASSETTES_DIR,
    Cassette,
    CassetteEntry,
    build_eval_server,
    cassette_path,
    request_key,
)
from evals.redaction import Redactor

RECORD_ENV = "JURIS_BRIDGE_EVALS_RECORD"

# One request per second: under DataJud's 120 per minute and gentle on the BNP and DJEN, whose
# limits are undocumented.
DEFAULT_MIN_INTERVAL_SECONDS = 1.0

_KEPT_HEADERS = ("content-type",)


@dataclass(frozen=True)
class RecordOptions:
    """How a recording session runs; the defaults are the real thing (tests override them).

    Attributes:
        environ: The environment checked for `JURIS_BRIDGE_EVALS_RECORD` (`os.environ` when None).
        inner: The transport under the recorder (a real HTTP one when None).
        today: The Cassette's recorded-on date (today when None).
        min_interval: The least seconds between two requests.
        clock: Monotonic clock for the pacing.
        sleep: Awaitable sleep for the pacing.
    """

    environ: Mapping[str, str] | None = None
    inner: httpx.AsyncBaseTransport | None = None
    today: date | None = None
    min_interval: float = DEFAULT_MIN_INTERVAL_SECONDS
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep


class RecordingDisabledError(RuntimeError):
    """Raised when recording is attempted without `JURIS_BRIDGE_EVALS_RECORD=1`."""


def recording_enabled(environ: Mapping[str, str] | None = None) -> bool:
    """Return whether the environment opts in to recording."""
    env = os.environ if environ is None else environ
    return env.get(RECORD_ENV) == "1"


def redact_body(redactor: Redactor, body: bytes, content_type: str) -> bytes:
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        return body
    if "json" in content_type.lower():
        try:
            data = json.loads(text)
        except ValueError:
            pass
        else:
            return json.dumps(redactor.redact(data), ensure_ascii=False).encode("utf-8")
    return redactor.redact(text).encode("utf-8")


class RecordingTransport(httpx.AsyncBaseTransport):
    """Forward to `inner`, pace the requests and record each redacted response."""

    def __init__(
        self,
        inner: httpx.AsyncBaseTransport,
        cassette: Cassette,
        *,
        min_interval: float = DEFAULT_MIN_INTERVAL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.inner = inner
        self.cassette = cassette
        self.min_interval = min_interval
        self._clock = clock
        self._sleep = sleep
        self._last: float | None = None
        self._redactor = Redactor()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Wait for the interval, forward the request, store the redacted response."""
        if self._last is not None:
            wait = self.min_interval - (self._clock() - self._last)
            if wait > 0:
                await self._sleep(wait)
        self._last = self._clock()
        response = await self.inner.handle_async_request(request)
        await response.aread()
        headers = {k: v for k, v in response.headers.items() if k.lower() in _KEPT_HEADERS}
        body = redact_body(self._redactor, response.content, headers.get("content-type", ""))
        key = request_key(request)
        self.cassette.entries[key] = CassetteEntry.from_response(
            key, response.status_code, headers, body
        )
        return httpx.Response(response.status_code, headers=headers, content=body)


@asynccontextmanager
async def recording_session(
    case_id: str, options: RecordOptions | None = None
) -> AsyncIterator[tuple[Client[Any], Cassette]]:
    """Yield an in-memory client over the real server and the Cassette it fills.

    Args:
        case_id: The Eval case id (named in the refusal message).
        options: Environment, transport, date and pacing; the real ones when None.

    Raises:
        RecordingDisabledError: `JURIS_BRIDGE_EVALS_RECORD` is not `1`; no transport is built.
    """
    options = options or RecordOptions()
    if not recording_enabled(options.environ):
        raise RecordingDisabledError(
            f"set {RECORD_ENV}=1 to record {case_id!r} from the live Sources "
            "(read-only, rate limited; see evals/README.md)"
        )
    cassette = Cassette(recorded_on=options.today or date.today())
    transport = RecordingTransport(
        options.inner if options.inner is not None else httpx.AsyncHTTPTransport(),
        cassette,
        min_interval=options.min_interval,
        clock=options.clock,
        sleep=options.sleep,
    )
    async with Client(build_eval_server(transport)) as client:
        yield client, cassette


async def record_case[T](
    case_id: str,
    run: Callable[[Client[Any]], Awaitable[T]],
    *,
    root: Path = CASSETTES_DIR,
    options: RecordOptions | None = None,
) -> Path:
    """Run `run(client)` on the real server over the recording transport; save the Cassette.

    Args:
        case_id: The Eval case id; names the file `<root>/<case_id>.json`.
        run: A coroutine function making the tool calls of the case.
        root: Folder of the Cassettes.
        options: See `RecordOptions`; the real ones when None.

    Returns:
        The path of the saved Cassette. Nothing is saved if `run` raises.
    """
    async with recording_session(case_id, options) as (client, cassette):
        await run(client)
    path = cassette_path(case_id, root=root)
    cassette.save(path)
    return path
