"""The agent loop against the real server over a Cassette, with a scripted model."""

import json
from datetime import date
from pathlib import Path

from evals.agent import run_agent, to_declaration
from evals.cassette import Cassette, CassetteEntry, replay_session
from evals.llm import ChatResult, Message, ScriptedLLMClient, ToolCall, Usage

DJEN_FIXTURE = (
    Path(__file__).parents[2] / "tests/contract/providers/djen/fixtures/tjsp_decisions.json"
)
CNJ = "1234567-76.2025.8.26.0100"
SEARCH = {
    "court": "tjsp",
    "date_from": "2026-10-15",
    "date_to": "2026-10-15",
    "cnj_number": CNJ,
}


async def _cassette_for(arguments: dict) -> Cassette:
    """A Cassette answering the request the search tool sends (learnt from its miss)."""
    async with replay_session(Cassette(date(2026, 10, 1))) as session:
        await session.client.call_tool("search_publications", arguments, raise_on_error=False)
        key = session.transport.missed[0]
    entry = CassetteEntry.from_response(key, 200, {}, DJEN_FIXTURE.read_bytes())
    return Cassette(date(2026, 10, 1), {key: entry})


def _calls(*calls: ToolCall, tokens=(10, 5)) -> ChatResult:
    return ChatResult(tool_calls=calls, usage=Usage(*tokens), key_alias="key-1")


def _answer(text: str, tokens=(20, 7)) -> ChatResult:
    return ChatResult(text=text, usage=Usage(*tokens), key_alias="key-1")


async def test_the_model_is_offered_the_servers_real_tools():
    llm = ScriptedLLMClient([_answer("ok")])
    async with replay_session(Cassette(date(2026, 10, 1))) as session:
        await run_agent("q", session, llm)
        served = {t.name for t in await session.client.list_tools()}

    offered = {t.name for t in llm.calls[0][1]}
    assert offered == served
    assert {"search_publications", "get_publication", "search_precedents"} <= offered


async def test_tools_can_be_limited_to_a_scope():
    llm = ScriptedLLMClient([_answer("ok")])
    async with replay_session(Cassette(date(2026, 10, 1))) as session:
        await run_agent("q", session, llm, tool_names={"list_coverage"})

    assert [t.name for t in llm.calls[0][1]] == ["list_coverage"]


async def test_a_declaration_is_a_plain_openapi_subset_of_the_tools_schema():
    async with replay_session(Cassette(date(2026, 10, 1))) as session:
        tool = next(t for t in await session.client.list_tools() if t.name == "search_publications")

    declaration = to_declaration(tool)

    text = json.dumps(declaration.parameters)
    assert declaration.name == "search_publications"
    assert declaration.description == tool.description
    assert "additionalProperties" not in text and "anyOf" not in text and '"default"' not in text
    assert declaration.parameters["properties"]["court"] == {
        "type": "string",
        "nullable": True,
    }
    assert declaration.parameters["required"] == ["date_from", "date_to"]


async def test_the_trajectory_records_calls_results_answer_and_usage():
    cassette = await _cassette_for(SEARCH)
    llm = ScriptedLLMClient(
        [_calls(ToolCall("search_publications", SEARCH)), _answer(f"Found {CNJ}.")]
    )
    async with replay_session(cassette) as session:
        trajectory = await run_agent("what came out?", session, llm, model="agent-m")

    tools = [s for s in trajectory.steps if s.kind == "tool"]
    models = [s for s in trajectory.steps if s.kind == "model"]
    assert [(s.name, s.input, s.error) for s in tools] == [("search_publications", SEARCH, None)]
    assert CNJ in tools[0].output
    assert trajectory.final_output == f"Found {CNJ}."
    assert [(m.model, m.usage.input_tokens, m.usage.output_tokens) for m in models] == [
        ("agent-m", 10, 5),
        ("agent-m", 20, 7),
    ]
    assert trajectory.total_usage().input_tokens == 30
    assert trajectory.final_state["cassette_misses"] == 0


async def test_the_tool_result_reaches_the_model():
    cassette = await _cassette_for(SEARCH)
    llm = ScriptedLLMClient([_calls(ToolCall("search_publications", SEARCH)), _answer("done")])
    async with replay_session(cassette) as session:
        await run_agent("q", session, llm)

    history = llm.calls[1][0]
    assert history[0] == Message(role="user", text="q")
    assert history[1].role == "assistant" and history[1].tool_calls[0].name == "search_publications"
    assert history[2].role == "tool" and history[2].tool_name == "search_publications"
    assert CNJ in history[2].text


async def test_a_tool_error_is_captured_and_the_loop_goes_on():
    llm = ScriptedLLMClient(
        [_calls(ToolCall("search_publications", {**SEARCH, "cnj_number": "bad"})), _answer("sorry")]
    )
    async with replay_session(Cassette(date(2026, 10, 1))) as session:
        trajectory = await run_agent("q", session, llm)

    step = next(s for s in trajectory.steps if s.kind == "tool")
    assert step.error and "invalid_argument" in step.error
    assert trajectory.final_output == "sorry"


async def test_an_unrecorded_request_is_counted_as_a_cassette_miss():
    llm = ScriptedLLMClient([_calls(ToolCall("search_publications", SEARCH)), _answer("none")])
    async with replay_session(Cassette(date(2026, 10, 1))) as session:
        trajectory = await run_agent("q", session, llm)

    step = next(s for s in trajectory.steps if s.kind == "tool")
    assert "source_unavailable" in step.error
    assert trajectory.final_state["cassette_misses"] == 1


async def test_an_unknown_tool_is_an_error_step_not_a_crash():
    llm = ScriptedLLMClient([_calls(ToolCall("no_such_tool", {})), _answer("hm")])
    async with replay_session(Cassette(date(2026, 10, 1))) as session:
        trajectory = await run_agent("q", session, llm)

    step = next(s for s in trajectory.steps if s.kind == "tool")
    assert step.name == "no_such_tool" and step.error


async def test_the_loop_stops_at_the_step_cap():
    looping = [_calls(ToolCall("list_coverage", {})) for _ in range(10)]
    llm = ScriptedLLMClient(looping)
    async with replay_session(Cassette(date(2026, 10, 1))) as session:
        trajectory = await run_agent("q", session, llm, max_steps=3)

    assert len(llm.calls) == 3
    assert sum(s.kind == "tool" for s in trajectory.steps) == 3
    assert trajectory.final_output is None
    assert trajectory.steps[-1].kind == "other" and "step cap" in trajectory.steps[-1].error


async def test_the_alias_of_the_key_behind_each_model_call_is_kept_in_the_final_state():
    cassette = await _cassette_for(SEARCH)
    llm = ScriptedLLMClient(
        [
            ChatResult(
                tool_calls=(ToolCall("search_publications", SEARCH),),
                usage=Usage(1, 1),
                key_alias="key-1",
            ),
            ChatResult(text="done", usage=Usage(1, 1), key_alias="key-2"),
        ]
    )
    async with replay_session(cassette) as session:
        trajectory = await run_agent("q", session, llm)

    assert trajectory.final_state["key_aliases"] == ["key-1", "key-2"]
