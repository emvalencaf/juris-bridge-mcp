import copy
import json
from datetime import datetime

import httpx
import pytest

TIMESTAMPS = ["2024-03-01T10:00:00.000000Z"] * 2 + [
    "2024-03-02T10:00:00.000000Z",
    "2024-03-03T10:00:00.000000Z",
    "2024-03-03T10:00:00.000000Z",
]


def _epoch_ms(stamp: str) -> int:
    return int(datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp() * 1000)


class PagingDatajud:
    """DataJud holding five cases (two pairs tie on `@timestamp`) that honours `search_after`."""

    def __init__(self, template: dict, total_relation: str = "eq") -> None:
        self.requests: list[httpx.Request] = []
        self.template = template
        self.relation = total_relation
        self.docs = []
        for index, stamp in enumerate(TIMESTAMPS):
            source = copy.deepcopy(template["hits"]["hits"][0]["_source"])
            source.update({"id": f"TRF1_G1_{index}", "@timestamp": stamp})
            self.docs.append(source)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        query = json.loads(request.content)
        ordered = sorted(self.docs, key=lambda d: (_epoch_ms(d["@timestamp"]), d["id"]))
        keyed = [(_epoch_ms(d["@timestamp"]), d["id"], d) for d in ordered]
        if "search_after" in query:
            after = tuple(query["search_after"])
            keyed = [k for k in keyed if k[:2] > after]
        hits = [
            {"_id": d["id"], "_source": d, "sort": [stamp, ident]}
            for stamp, ident, d in keyed[: query["size"]]
        ]
        body = {
            "timed_out": False,
            "hits": {
                "total": {"value": len(self.docs), "relation": self.relation},
                "hits": hits,
            },
        }
        return httpx.Response(200, json=body)


@pytest.fixture
def paging(datajud, server_args):
    fake = PagingDatajud(datajud.body)
    server_args["transport"] = httpx.MockTransport(fake)
    return fake


async def _call(client, **arguments):
    result = await client.call_tool("search_cases", arguments, raise_on_error=False)
    if result.is_error:
        return json.loads(result.content[0].text)
    return result.data


async def test_pages_through_every_case_once_in_a_stable_order(paging, mcp_client):
    seen, cursor = [], None
    while True:
        page = await _call(mcp_client, court="trf1", limit=2, cursor=cursor)
        seen += [item["last_updated_at"] for item in page["items"]]
        assert page["total"] == 5 and page["total_is_lower_bound"] is False
        cursor = page["next_cursor"]
        if cursor is None:
            break

    assert len(seen) == 5
    sorted_ids = sorted(paging.docs, key=lambda d: (d["@timestamp"], d["id"]))
    assert [r.url.path for r in paging.requests] == ["/api_publica_trf1/_search"] * 3
    assert json.loads(paging.requests[0].content)["sort"] == [
        {"@timestamp": {"order": "asc"}},
        {"id.keyword": {"order": "asc"}},
    ]
    assert json.loads(paging.requests[1].content)["search_after"] == [
        _epoch_ms(sorted_ids[1]["@timestamp"]),
        sorted_ids[1]["id"],
    ]


async def test_cursor_alone_resumes_on_the_court_it_carries(paging, mcp_client):
    first = await _call(mcp_client, court="trf1", limit=2)

    second = await _call(mcp_client, cursor=first["next_cursor"])

    assert second["court"] == "trf1" and len(second["items"]) == 3
    assert second["next_cursor"] is None


async def test_items_are_normalized_cases_without_events(paging, mcp_client):
    page = await _call(mcp_client, court="trf1", limit=1)

    item = page["items"][0]
    assert page["source"] == "datajud" and page["content_kind"] == "metadata"
    assert page["retrieved_at"].endswith("Z")
    assert item["citation"] == {"text": "DataJud · TRF1 · 0000832-35.2018.4.01.3202", "url": None}
    assert item["class"] == {"code": 436, "name": "Procedimento do Juizado Especial Cível"}
    assert "events" not in item and "hint" not in page


async def test_filters_become_a_filter_query(paging, mcp_client):
    await _call(
        mcp_client,
        court="trf1",
        case_class=436,
        judging_body=16403,
        subject=6177,
        filed_from="2018-10-01",
        filed_to="2018-10-31",
    )

    clauses = json.loads(paging.requests[0].content)["query"]["bool"]["filter"]
    assert {"term": {"classe.codigo": 436}} in clauses
    assert {"term": {"orgaoJulgador.codigo": 16403}} in clauses
    assert {"term": {"assuntos.codigo": 6177}} in clauses
    assert {
        "range": {
            "dataAjuizamento": {
                "gte": "20181001000000",
                "lte": "20181031235959",
                "format": "yyyyMMddHHmmss",
            }
        }
    } in clauses


async def test_the_ten_thousand_cap_sets_the_lower_bound_and_a_hint(server_args, datajud):
    fake = PagingDatajud(datajud.body, total_relation="gte")
    fake.docs = fake.docs[:1]
    server_args["transport"] = httpx.MockTransport(fake)
    from fastmcp import Client

    from juris_bridge_mcp.infrastructure.bootstrap import build_server

    async with Client(build_server(**server_args)) as client:
        page = await _call(client, court="trf1")

    assert page["total_is_lower_bound"] is True
    assert "narrow" in page["hint"]


async def test_an_empty_search_is_not_an_error(mcp_client, datajud):
    datajud.body = datajud.fixture("trf1_empty.json")

    page = await _call(mcp_client, court="trf1")

    assert page["items"] == [] and page["total"] == 0 and page["next_cursor"] is None


async def test_unknown_court_is_invalid_with_valid_aliases(mcp_client, datajud):
    error = await _call(mcp_client, court="nope")

    assert error["code"] == "invalid_argument" and "tjsp" in error["hint"]
    assert datajud.requests == []


@pytest.mark.parametrize(
    "arguments",
    [{"court": "trf1", "limit": 0}, {"court": "trf1", "limit": 51}, {"cursor": "garbage"}, {}],
)
async def test_bad_arguments_make_no_call(mcp_client, datajud, arguments):
    error = await _call(mcp_client, **arguments)

    assert error["code"] == "invalid_argument"
    assert datajud.requests == []
