import base64
import json

import pytest

from tests.integration.mcp.conftest import FakeDjen


async def _search_ids(client) -> list[str]:
    result = await client.call_tool(
        "search_publications",
        {
            "court": "tjsp",
            "date_from": "2026-10-14",
            "date_to": "2026-10-15",
            "query": "recurso especial",
        },
    )
    return [item["id"] for item in result.data["items"]]


async def _id_with_hash(client, item_hash: str) -> str:
    ids = await _search_ids(client)
    return next(i for i in ids if _decoded_hash(i) == item_hash)


def _decoded_hash(publication_id: str) -> str:
    padded = publication_id + "=" * (-len(publication_id) % 4)
    return base64.urlsafe_b64decode(padded).decode().split("|", 3)[3]


async def _error(client, **arguments) -> dict:
    result = await client.call_tool("get_publication", arguments, raise_on_error=False)
    assert result.is_error
    return json.loads(result.content[0].text)


async def test_returns_the_plain_text_of_a_plain_item(djen: FakeDjen, mcp_client):
    publication_id = await _id_with_hash(mcp_client, "hashdecision0001")

    result = await mcp_client.call_tool("get_publication", {"id": publication_id})

    full = result.data
    assert full["content_kind"] == "full_text" and full["source"] == "djen"
    assert full["text"].startswith("DECISÃO Vistos.") and full["truncated"] is False
    assert full["text_length"] == len(full["text"]) and full["next_cursor"] is None
    assert full["citation"]["text"].startswith("TJSP, DESPACHO/DECISÃO")
    assert full["id"] == publication_id


async def test_strips_the_html_of_an_html_item(djen: FakeDjen, mcp_client):
    publication_id = await _id_with_hash(mcp_client, "hashruling000002")

    result = await mcp_client.call_tool("get_publication", {"id": publication_id})

    assert "<" not in result.data["text"] and "RECURSO ESPECIAL & honorários" in result.data["text"]


async def test_reads_a_long_html_text_through_its_cursor(djen: FakeDjen, mcp_client):
    publication_id = await _id_with_hash(mcp_client, "hashruling000002")
    words = [f"palavra{i}" for i in range(8000)]
    expected = " ".join(words)
    djen.body["items"][1]["texto"] = "<html><body>" + "".join(f"<p>{w}</p>" for w in words)
    assert len(expected) > 60000

    pieces, cursor = [], None
    while True:
        arguments = {"id": publication_id, **({"cursor": cursor} if cursor else {})}
        slice_ = (await mcp_client.call_tool("get_publication", arguments)).data
        pieces.append(slice_["text"])
        assert slice_["text_length"] == len(expected)
        cursor = slice_["next_cursor"]
        if not slice_["truncated"]:
            break

    assert len(pieces) > 5 and " ".join(pieces) == expected


async def test_an_item_gone_is_not_found(djen: FakeDjen, mcp_client):
    publication_id = await _id_with_hash(mcp_client, "hashdecision0001")
    djen.body = FakeDjen.fixture("empty.json")

    assert (await _error(mcp_client, id=publication_id))["code"] == "not_found"


@pytest.mark.parametrize("status, code", [(503, "source_unavailable"), (403, "source_blocked")])
async def test_source_errors_map_as_in_the_search(djen: FakeDjen, mcp_client, status, code):
    publication_id = await _id_with_hash(mcp_client, "hashdecision0001")
    djen.status = status

    assert (await _error(mcp_client, id=publication_id))["code"] == code


async def test_rejects_a_malformed_id_and_cursor(djen: FakeDjen, mcp_client):
    publication_id = await _id_with_hash(mcp_client, "hashdecision0001")

    assert (await _error(mcp_client, id="zzz"))["code"] == "invalid_argument"
    assert (await _error(mcp_client, id=publication_id, cursor="zzz"))["code"] == (
        "invalid_argument"
    )
