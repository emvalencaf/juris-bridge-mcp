"""The wide event of the current request, built in a contextvar (ADR 0004).

Handlers and tools only add business context through the helpers below. Each helper
takes named, allow-listed fields so request content (search text, CNJ numbers, party
names, `include_raw` content, payloads, upstream error bodies) has no way in. Outside
a request (unit tests, the in-memory client) every helper is a no-op.
"""

import logging
import sys
from collections.abc import Mapping
from contextvars import ContextVar, Token
from typing import Any

from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure

LOGGER_NAME = "juris_bridge_mcp.wide_event"
MAX_UPSTREAM_ENTRIES = 10

_logger = logging.getLogger(LOGGER_NAME)
_cold_start = True


class WideEvent:
    """The mutable record of one request; the middleware emits it exactly once."""

    def __init__(self, environment: Mapping[str, Any], request_id: str) -> None:
        global _cold_start  # the first event of the process is the cold start
        self.fields: dict[str, Any] = {
            **environment,
            "cold_start": _cold_start,
            "request_id": request_id,
        }
        _cold_start = False
        self.upstream: list[dict[str, Any]] = []

    def finish(self, *, status: int, duration_ms: float) -> dict[str, Any]:
        """Return the complete event, with the outcome derived from what was recorded."""
        http = {**self.fields.get("http", {}), "status": status}
        error = self.fields.get("error")
        event = {**self.fields, "http": http, "outcome": _outcome(status, error)}
        event["duration_ms"] = round(duration_ms, 1)
        if self.upstream:
            event["upstream"] = list(self.upstream)
        return event


def _outcome(status: int, error: Mapping[str, Any] | None) -> str:
    if status == 401:
        return "unauthorized"
    if status == 429 or (error is not None and error.get("code") == ErrorCode.RATE_LIMITED):
        return "rate_limited"
    if status >= 400 or error is not None:
        return "error"
    return "success"


_current: ContextVar[WideEvent | None] = ContextVar("wide_event", default=None)


def start(event: WideEvent) -> Token[WideEvent | None]:
    """Make `event` the current one; hand the token to `stop`."""
    return _current.set(event)


def stop(token: Token[WideEvent | None]) -> None:
    """Forget the current event."""
    _current.reset(token)


def _merge(section: str, **fields: Any) -> None:
    event = _current.get()
    if event is not None:
        event.fields.setdefault(section, {}).update(
            {k: v for k, v in fields.items() if v is not None}
        )


def annotate_request(*, method: str, user_agent: str | None) -> None:
    """Record the HTTP method and caller user agent."""
    _merge("http", method=method)
    event = _current.get()
    if event is not None and user_agent:
        event.fields["user_agent"] = user_agent[:256]


def annotate_mcp(*, method: str | None, tool: str | None) -> None:
    """Record the JSON-RPC method and, for `tools/call`, the tool name."""
    _merge("mcp", method=method)
    _merge("tool", name=tool)


def set_caller(key_id: str) -> None:
    """Record the first 8 hex of the SHA-256 of a valid API key; never call it otherwise."""
    _merge("caller", key_id=key_id)


def annotate(
    *,
    source: str | None = None,
    court: str | None = None,
    result_count: int | None = None,
    cache: str | None = None,
    paginated: bool | None = None,
    call_shape: Mapping[str, Any] | None = None,
) -> None:
    """Add tool business context: only the shape of a call, never its content."""
    event = _current.get()
    if event is None:
        return
    for key, value in (
        ("source", source),
        ("court", court),
        ("result_count", result_count),
        ("cache", cache),
        ("paginated", paginated),
    ):
        if value is not None:
            event.fields[key] = value
    if call_shape:
        _merge("call_shape", **call_shape)


def record_failure(failure: ToolFailure) -> None:
    """Record a tool failure's Error code and retryability (never its message)."""
    _merge("error", code=failure.code.value, retryable=failure.retryable)
    event = _current.get()
    if event is not None and failure.source is not None:
        event.fields.setdefault("source", failure.source)


def record_upstream(*, source: str, status: int | None, duration_ms: float, retries: int) -> None:
    """Add one upstream call to the event's short `upstream` list."""
    event = _current.get()
    if event is not None and len(event.upstream) < MAX_UPSTREAM_ENTRIES:
        event.upstream.append(
            {
                "source": source,
                "status": status,
                "duration_ms": round(duration_ms, 1),
                "retries": retries,
            }
        )


def configure_logger() -> None:
    """Send wide events to stdout as bare JSON lines; safe to call more than once."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.handlers[:] = [handler]
    _logger.setLevel(logging.INFO)
    _logger.propagate = False
