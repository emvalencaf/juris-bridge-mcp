import json

import pytest

from juris_bridge_mcp.adapters import wide_event
from juris_bridge_mcp.adapters.wide_event import MAX_UPSTREAM_ENTRIES, WideEvent, _outcome
from juris_bridge_mcp.adapters.wide_event_middleware import _MAX_BODY_BYTES, WideEventMiddleware


@pytest.fixture
def event():
    current = WideEvent({}, "r")
    token = wide_event.start(current)
    yield current
    wide_event.stop(token)


@pytest.mark.parametrize(
    ("status", "error", "expected"),
    [
        (200, None, "success"),
        (401, None, "unauthorized"),
        (429, None, "rate_limited"),
        (200, {"code": "rate_limited"}, "rate_limited"),
        (200, {"code": "not_found"}, "error"),
        (405, None, "error"),
        (500, None, "error"),
    ],
)
def test_outcome(status, error, expected):
    assert _outcome(status, error) == expected


def test_upstream_is_capped_and_flagged(event):
    for _ in range(MAX_UPSTREAM_ENTRIES + 3):
        wide_event.record_upstream(source="datajud", status=200, duration_ms=1, retries=0)

    done = event.finish(status=200, duration_ms=1)

    assert len(done["upstream"]) == MAX_UPSTREAM_ENTRIES
    assert done["upstream_truncated"] is True


def test_short_upstream_list_is_not_flagged(event):
    wide_event.record_upstream(source="datajud", status=200, duration_ms=1, retries=0)

    assert "upstream_truncated" not in event.finish(status=200, duration_ms=1)


def test_helpers_are_no_ops_outside_a_request():
    wide_event.annotate(source="datajud", cache="hit")
    wide_event.record_upstream(source="datajud", status=200, duration_ms=1, retries=0)
    wide_event.set_caller("abcd1234")


def _mcp_of(body: bytes, method: str = "POST") -> dict:
    current = WideEvent({}, "r")
    token = wide_event.start(current)
    try:
        WideEventMiddleware._annotate_mcp({"method": method}, body)
    finally:
        wide_event.stop(token)
    return {k: v for k, v in current.fields.items() if k in {"mcp", "tool"}}


def test_tools_call_body_yields_method_and_tool():
    body = json.dumps({"method": "tools/call", "params": {"name": "search"}}).encode()

    assert _mcp_of(body) == {"mcp": {"method": "tools/call"}, "tool": {"name": "search"}}


@pytest.mark.parametrize("body", [b"not json", b"[1, 2]", b'"text"', b""])
def test_unparseable_bodies_add_nothing(body):
    assert _mcp_of(body) == {}


def test_get_requests_are_not_parsed():
    assert _mcp_of(b'{"method": "tools/list"}', method="GET") == {}


def test_oversized_body_is_flagged_not_parsed():
    body = b'{"method": "tools/list", "pad": "' + b"x" * _MAX_BODY_BYTES + b'"}'

    assert _mcp_of(body) == {"mcp": {"body_oversized": True}}


def test_non_string_tool_name_is_ignored():
    body = json.dumps({"method": "tools/call", "params": {"name": 5}}).encode()

    assert _mcp_of(body) == {"mcp": {"method": "tools/call"}}
