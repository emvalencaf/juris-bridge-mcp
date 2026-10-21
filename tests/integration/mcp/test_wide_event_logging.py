import hashlib
import json
import logging
import re
from contextlib import asynccontextmanager

import httpx
import pytest
from fastmcp import FastMCP
from starlette.middleware import Middleware

from juris_bridge_mcp.adapters import wide_event
from juris_bridge_mcp.adapters.bearer_auth import BearerAuthMiddleware
from juris_bridge_mcp.adapters.wide_event_middleware import WideEventMiddleware
from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure, to_tool_error
from juris_bridge_mcp.infrastructure.bootstrap import build_http_app

ENVIRONMENT = {
    "service": "juris-bridge-mcp",
    "version": "9.9.9",
    "commit_hash": "abc1234",
    "region": "sa-east-1",
}
HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
SEARCH_TEXT = "João da Silva 0001234-56.2020.8.26.0100"


def _call(name: str, arguments: dict, id_: int = 1) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": id_,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }


def _build_app(keys=("key-one",)):
    server = FastMCP("t")

    @server.tool
    def search(text: str) -> dict:
        wide_event.annotate(
            source="datajud",
            court="tjsp",
            result_count=3,
            cache="miss",
            paginated=True,
            call_shape={"filters": ["court", "class"], "limit": 10, "cursor_sent": False},
        )
        wide_event.record_upstream(source="datajud", status=200, duration_ms=12.34, retries=1)
        return {"echo": text, "payload": "RESPONSE-PAYLOAD"}

    @server.tool
    def fail() -> str:
        wide_event.record_upstream(source="datajud", status=429, duration_ms=5, retries=2)
        failure = ToolFailure(
            ErrorCode.RATE_LIMITED,
            "UPSTREAM-ERROR-BODY",
            source="datajud",
            retryable=True,
            retry_after_seconds=3,
        )
        wide_event.record_failure(failure)
        raise to_tool_error(failure)

    return server.http_app(
        path="/mcp",
        stateless_http=True,
        json_response=True,
        middleware=[
            Middleware(WideEventMiddleware, environment=ENVIRONMENT),
            Middleware(BearerAuthMiddleware, keys=keys),
        ],
    )


@asynccontextmanager
async def _client(app):
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest.fixture
def events(caplog):
    caplog.set_level(logging.INFO, logger=wide_event.LOGGER_NAME)

    def read() -> list[dict]:
        return [
            json.loads(r.getMessage()) for r in caplog.records if r.name == wide_event.LOGGER_NAME
        ]

    return read


def _auth(key="key-one", **extra):
    return {**HEADERS, "Authorization": f"Bearer {key}", **extra}


async def test_one_event_per_request_with_environment_and_request_shape(events):
    async with _client(_build_app()) as client:
        response = await client.post(
            "/mcp",
            json=_call("search", {"text": SEARCH_TEXT}),
            headers=_auth(**{"user-agent": "agent/1.0", "x-amzn-requestid": "aws-req-1"}),
        )

    assert response.status_code == 200
    (event,) = events()
    assert event["service"] == "juris-bridge-mcp"
    assert event["version"] == "9.9.9"
    assert event["commit_hash"] == "abc1234"
    assert event["region"] == "sa-east-1"
    assert event["request_id"] == "aws-req-1"
    assert isinstance(event["cold_start"], bool)
    assert event["http"] == {"method": "POST", "status": 200}
    assert event["mcp"] == {"method": "tools/call"}
    assert event["tool"] == {"name": "search"}
    assert event["outcome"] == "success"
    assert event["duration_ms"] >= 0
    assert event["user_agent"] == "agent/1.0"


async def test_request_id_falls_back_to_a_uuid(events):
    async with _client(_build_app()) as client:
        await client.post("/mcp", json=_call("search", {"text": "x"}), headers=_auth())

    assert re.fullmatch(r"[0-9a-f-]{36}", events()[0]["request_id"])


async def test_cold_start_only_on_the_first_event(events, monkeypatch):
    monkeypatch.setattr(wide_event, "_cold_start", True)
    async with _client(_build_app()) as client:
        await client.post("/mcp", json=_call("search", {"text": "x"}), headers=_auth())
        await client.post("/mcp", json=_call("search", {"text": "x"}, 2), headers=_auth())

    assert [e["cold_start"] for e in events()] == [True, False]


async def test_tools_add_business_context_and_upstream(events):
    async with _client(_build_app()) as client:
        await client.post("/mcp", json=_call("search", {"text": "x"}), headers=_auth())

    (event,) = events()
    assert event["source"] == "datajud"
    assert event["court"] == "tjsp"
    assert event["result_count"] == 3
    assert event["cache"] == "miss"
    assert event["paginated"] is True
    assert event["call_shape"] == {"filters": ["court", "class"], "limit": 10, "cursor_sent": False}
    assert event["upstream"] == [
        {"source": "datajud", "status": 200, "duration_ms": 12.3, "retries": 1}
    ]


async def test_tool_failure_records_code_and_retryable_but_not_the_message(events):
    async with _client(_build_app()) as client:
        response = await client.post("/mcp", json=_call("fail", {}), headers=_auth())

    assert response.json()["result"]["isError"] is True
    (event,) = events()
    assert event["error"] == {"code": "rate_limited", "retryable": True}
    assert event["outcome"] == "rate_limited"
    assert "UPSTREAM-ERROR-BODY" not in json.dumps(event)


async def test_caller_key_id_is_the_first_8_hex_of_the_sha256(events):
    async with _client(_build_app()) as client:
        await client.post("/mcp", json=_call("search", {"text": "x"}), headers=_auth())

    assert events()[0]["caller"] == {"key_id": hashlib.sha256(b"key-one").hexdigest()[:8]}


async def test_invalid_key_is_unauthorized_and_records_no_caller(events):
    async with _client(_build_app()) as client:
        response = await client.post(
            "/mcp", json=_call("search", {"text": "x"}), headers=_auth("wrong")
        )

    assert response.status_code == 401
    (event,) = events()
    assert event["outcome"] == "unauthorized"
    assert event["http"]["status"] == 401
    assert "caller" not in event
    assert "wrong" not in json.dumps(event)


async def test_never_logged_content_is_absent(events):
    async with _client(_build_app()) as client:
        await client.post(
            "/mcp",
            json=_call("search", {"text": SEARCH_TEXT, "include_raw": True}),
            headers=_auth(),
        )

    line = json.dumps(events())
    for forbidden in ("João", "0001234-56", "RESPONSE-PAYLOAD", "include_raw", "key-one"):
        assert forbidden not in line


async def test_each_request_gets_its_own_event(events):
    async with _client(_build_app()) as client:
        await client.get("/mcp", headers=_auth())
        await client.post("/mcp", json=_call("search", {"text": "x"}), headers=_auth())

    first, second = events()
    assert first["http"]["method"] == "GET"
    assert first["http"]["status"] == 405
    assert first["outcome"] == "error"
    assert "mcp" not in first
    assert second["tool"] == {"name": "search"}
    assert "upstream" not in first


async def test_unhandled_exception_still_emits_one_error_event(events, caplog):
    async def boom(scope, receive, send):
        raise RuntimeError("kaboom")

    app = WideEventMiddleware(boom, environment=ENVIRONMENT)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/")

    (event,) = events()
    assert event["http"]["status"] == 500
    assert event["outcome"] == "error"
    assert [r.levelno for r in caplog.records if r.name == wide_event.LOGGER_NAME] == [
        logging.ERROR
    ]


async def test_real_bootstrap_app_emits_the_event_for_list_coverage(events, server_args):
    app = build_http_app(("key-one",), ENVIRONMENT, **server_args)
    async with _client(app) as client:
        await client.post("/mcp", json=_call("list_coverage", {}), headers=_auth())

    (event,) = events()
    assert event["tool"] == {"name": "list_coverage"}
    assert event["version"] == "9.9.9"


def test_configure_logger_writes_bare_json_to_stdout(capsys):
    wide_event.configure_logger()
    wide_event.configure_logger()

    logging.getLogger(wide_event.LOGGER_NAME).info(json.dumps({"a": 1}))

    assert capsys.readouterr().out == '{"a": 1}\n'


def test_call_shape_drops_keys_outside_the_allow_list():
    event = wide_event.WideEvent({}, "r")
    token = wide_event.start(event)
    try:
        wide_event.annotate(call_shape={"limit": 5, "query": "João da Silva", "year": 2020})
    finally:
        wide_event.stop(token)

    assert event.fields["call_shape"] == {"limit": 5, "year": 2020}


async def test_search_publications_records_its_shape_but_not_the_query(events, server_args):
    app = build_http_app(("key-one",), ENVIRONMENT, **server_args)
    arguments = {
        "court": "tjsp",
        "date_from": "2026-10-15",
        "date_to": "2026-10-15",
        "query": "Maria Aparecida dos Santos",
        "limit": 5,
    }
    async with _client(app) as client:
        await client.post("/mcp", json=_call("search_publications", arguments), headers=_auth())

    (event,) = events()
    assert event["tool"] == {"name": "search_publications"}
    assert event["source"] == "djen" and event["court"] == "tjsp"
    assert event["result_count"] == 2
    assert event["call_shape"] == {"court_alias": "tjsp", "limit": 5, "cursor_sent": False}
    assert "Maria Aparecida" not in json.dumps(event)
