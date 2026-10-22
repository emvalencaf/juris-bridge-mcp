import json
import os
import subprocess
import sys

import pytest
from fastmcp import Client, FastMCP

from juris_bridge_mcp import main as entrypoint
from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure, to_tool_error

INIT = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "t", "version": "0"},
    },
}
HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


def _auth(key: str) -> dict[str, str]:
    return {**HEADERS, "Authorization": f"Bearer {key}"}


async def test_tools_are_exposed_and_read_only(mcp_client):
    tools = await mcp_client.list_tools()

    assert sorted(t.name for t in tools) == [
        "get_case",
        "get_legislation",
        "get_precedent",
        "get_publication",
        "list_coverage",
        "search_cases",
        "search_legislation",
        "search_precedents",
        "search_publications",
    ]
    assert all(t.annotations.read_only_hint is True for t in tools)


async def test_list_coverage_reports_sources(mcp_client):
    result = await mcp_client.call_tool("list_coverage", {})

    assert {s["source"] for s in result.data["sources"]} == {"datajud", "djen", "senado", "bnp"}


async def test_list_coverage_reports_the_bnp_bodies(mcp_client):
    result = await mcp_client.call_tool("list_coverage", {})

    bnp = next(s for s in result.data["sources"] if s["source"] == "bnp")
    courts = {c["alias"]: c for c in bnp["courts"]}
    assert bnp["kind"] == "precedents" and len(courts) == 93
    assert courts["stf"]["supported"] is True and courts["trf1"]["supported"] is True
    assert courts["TNU"]["supported"] is True and "no Court alias" in courts["TNU"]["reason"]


async def test_missing_key_gets_401(asgi_client):
    async with asgi_client() as client:
        response = await client.post("/mcp", json=INIT, headers=HEADERS)

        assert response.status_code == 401


async def test_wrong_key_gets_401(asgi_client):
    async with asgi_client() as client:
        response = await client.post("/mcp", json=INIT, headers=_auth("nope"))

        assert response.status_code == 401


async def test_non_bearer_scheme_gets_401(asgi_client):
    async with asgi_client() as client:
        headers = {**HEADERS, "Authorization": "Basic key-one"}

        assert (await client.post("/mcp", json=INIT, headers=headers)).status_code == 401


@pytest.mark.parametrize("key", ["key-one", "key-two"])
async def test_each_configured_key_is_accepted(asgi_client, key):
    async with asgi_client() as client:
        response = await client.post("/mcp", json=INIT, headers=_auth(key))

        assert response.status_code == 200


async def test_responses_are_json_without_a_session_id(asgi_client):
    async with asgi_client() as client:
        response = await client.post("/mcp", json=INIT, headers=_auth("key-one"))

        assert response.headers["content-type"].startswith("application/json")
        assert "mcp-session-id" not in response.headers
        assert json.loads(response.text)["result"]["serverInfo"]["name"] == "juris-bridge-mcp"


async def test_get_answers_405(asgi_client):
    async with asgi_client() as client:
        response = await client.get("/mcp", headers=_auth("key-one"))

        assert response.status_code == 405


async def test_tool_call_works_without_a_prior_session(asgi_client):
    async with asgi_client() as client:
        call = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "list_coverage", "arguments": {}},
        }

        response = await client.post("/mcp", json=call, headers=_auth("key-one"))

        assert response.status_code == 200
        assert response.json()["result"]["isError"] is False


def test_server_refuses_to_start_without_api_key():
    env = {k: v for k, v in os.environ.items() if not k.startswith("JURIS_BRIDGE_")}
    result = subprocess.run(
        [sys.executable, "-m", "juris_bridge_mcp.main"],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode != 0
    assert "API_KEYS" in result.stderr


async def test_tool_failure_is_an_mcp_error_with_the_documented_shape():
    server = FastMCP("t")

    @server.tool
    def boom() -> str:
        raise to_tool_error(
            ToolFailure(
                ErrorCode.RATE_LIMITED,
                "slow down",
                source="datajud",
                retryable=True,
                retry_after_seconds=3,
            )
        )

    async with Client(server) as client:
        result = await client.call_tool("boom", {}, raise_on_error=False)

    assert result.is_error is True
    assert json.loads(result.content[0].text) == {
        "code": "rate_limited",
        "message": "slow down",
        "source": "datajud",
        "retryable": True,
        "retry_after_seconds": 3,
    }


def test_startup_prints_one_line_notice_without_prompting(monkeypatch, capsys):
    monkeypatch.setenv("JURIS_BRIDGE_SERVER_API_KEYS", "k")
    monkeypatch.setattr(entrypoint.uvicorn, "run", lambda *a, **k: None)

    entrypoint.main()

    out = capsys.readouterr().out.strip().splitlines()
    assert out == [entrypoint.NOTICE]
