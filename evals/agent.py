"""The agent loop: model, tool calls, the server's tools, results, until an answer or the cap.

Our own loop, a few dozen lines: assayer scores a Trajectory but does not build one. It lists
the real tools of the server over the in-memory MCP client of a `ReplaySession`, offers them
to the model as `ToolDeclaration`s and records every call, its arguments, its result or
error, the final answer and the token usage as an assayer `Trajectory`.
"""

import asyncio
from collections.abc import Collection
from typing import Any

from assayer.models import Step, TokenUsage, Trajectory

from evals.cassette import ReplaySession
from evals.llm import LLMClient, Message, ToolDeclaration

DEFAULT_MAX_STEPS = 8

# The tools the first version evaluates: Publications, Precedents and the Coverage.
IN_SCOPE_TOOLS = frozenset(
    {
        "list_coverage",
        "search_publications",
        "get_publication",
        "search_precedents",
        "get_precedent",
    }
)

SYSTEM_PROMPT = (
    "You help a lawyer find Brazilian judicial information. Use the tools you are given; "
    "answer only from what they return. If they return nothing relevant, say so instead of "
    "guessing. Cite a CNJ number or a Precedent only if a tool returned it."
)

# JSON Schema keywords Gemini's OpenAPI subset does not accept.
_DROPPED = frozenset({"additionalProperties", "default", "title", "format", "$defs", "examples"})


def to_declaration(tool: Any) -> ToolDeclaration:
    """Convert an MCP tool into the declaration the model reads.

    Args:
        tool: An MCP tool with `name`, `description` and an input schema.

    Returns:
        The declaration, its JSON Schema reduced to the OpenAPI subset the model accepts.
    """
    schema = getattr(tool, "input_schema", None) or tool.inputSchema
    return ToolDeclaration(tool.name, tool.description or "", _simplify(schema))


def _simplify(schema: Any) -> Any:
    """Drop unsupported keywords and turn `anyOf [X, null]` into `X` with `nullable`."""
    if isinstance(schema, list):
        return [_simplify(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    options = schema.get("anyOf")
    if options:
        real = [o for o in options if o != {"type": "null"}]
        merged = {k: v for k, v in schema.items() if k != "anyOf"}
        if len(real) == 1:
            merged.update(_simplify(real[0]))
            if len(real) != len(options):
                merged["nullable"] = True
            return _simplify_keys(merged)
        merged["anyOf"] = [_simplify(o) for o in real]
        return _simplify_keys(merged)
    return _simplify_keys(schema)


def _simplify_keys(schema: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in schema.items():
        if key in _DROPPED:
            continue
        if key == "properties":
            out[key] = {name: _simplify(sub) for name, sub in value.items()}
        else:
            out[key] = _simplify(value) if key in {"items", "anyOf"} else value
    return out


async def run_agent(
    question: str,
    session: ReplaySession,
    llm: LLMClient,
    *,
    max_steps: int = DEFAULT_MAX_STEPS,
    tool_names: Collection[str] | None = None,
    system: str = SYSTEM_PROMPT,
    model: str | None = None,
) -> Trajectory:
    """Put one question to the model, with the server's tools, and record what happened.

    Args:
        question: The Eval case's question.
        session: The in-memory client over the real server, fed by a Cassette.
        llm: The model client (scripted in tests).
        max_steps: The most model calls; the loop stops there without an answer.
        tool_names: Offer only these tools; all the server's tools when None.
        system: The system instruction.
        model: The model name, kept on each model Step.

    Returns:
        The Trajectory: a model Step per model call (with its usage) and a tool Step per
        tool call (`input` the arguments, `output` the result text, `error` the failure),
        the final answer, and `final_state`: the cassette-miss count and `key_aliases`, the alias
        of the key that served each model call, in order (never the key itself).
    """
    served = await session.client.list_tools()
    tools = [to_declaration(t) for t in served if tool_names is None or t.name in tool_names]
    messages = [Message(role="user", text=question)]
    steps: list[Step] = []
    key_aliases: list[str] = []
    final_output: str | None = None

    for _ in range(max_steps):
        reply = await asyncio.to_thread(llm.chat, messages, tools, system=system)
        if reply.key_alias:
            key_aliases.append(reply.key_alias)
        steps.append(
            Step(
                kind="model",
                model=model,
                input=messages[-1].text,
                output=reply.text or None,
                usage=TokenUsage(reply.usage.input_tokens, reply.usage.output_tokens, None),
            )
        )
        if not reply.tool_calls:
            final_output = reply.text
            break
        messages.append(Message(role="assistant", text=reply.text, tool_calls=reply.tool_calls))
        for call in reply.tool_calls:
            text, error = await _call_tool(session, call.name, call.arguments)
            steps.append(
                Step(kind="tool", name=call.name, input=call.arguments, output=text, error=error)
            )
            messages.append(Message(role="tool", text=text, tool_name=call.name))
    else:
        steps.append(Step(kind="other", error=f"step cap of {max_steps} model calls reached"))

    return Trajectory(
        steps=steps,
        final_output=final_output,
        final_state={"cassette_misses": session.misses, "key_aliases": key_aliases},
    )


async def _call_tool(
    session: ReplaySession, name: str, arguments: dict[str, Any]
) -> tuple[str, str | None]:
    """Call one tool; return the text the model sees and the error, if it failed."""
    try:
        result = await session.client.call_tool(name, arguments, raise_on_error=False)
    except Exception as exc:  # unknown tool, bad arguments: data for the Trajectory
        message = f"{type(exc).__name__}: {exc}"
        return message, message
    text = "\n".join(block.text for block in result.content if hasattr(block, "text"))
    return text, (text or "tool error") if result.is_error else None
