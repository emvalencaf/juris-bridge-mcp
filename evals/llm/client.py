"""The provider-neutral types and the `LLMClient` Protocol injected into the agent and the judge."""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol


@dataclass(frozen=True)
class ToolCall:
    """A tool the model asked to call.

    Attributes:
        name: The tool name.
        arguments: The JSON arguments.
        signature: Opaque provider token that must be sent back with the call, if any.
    """

    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    signature: str | None = None


@dataclass(frozen=True)
class Message:
    """One turn of the conversation.

    Attributes:
        role: `user`, `assistant` or `tool` (the result of a tool call).
        text: The text; for a `tool` message, the tool result.
        tool_calls: The calls an `assistant` message made.
        tool_name: For a `tool` message, the name of the tool that produced `text`.
    """

    role: Literal["user", "assistant", "tool"]
    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    tool_name: str | None = None


@dataclass(frozen=True)
class ToolDeclaration:
    """A tool offered to the model.

    Attributes:
        name: The tool name.
        description: What the tool does, as the model reads it.
        parameters: JSON Schema of the arguments (an OpenAPI subset for Gemini).
    """

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Usage:
    """Tokens one call used."""

    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        """Input plus output tokens."""
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True)
class ChatResult:
    """What the model answered.

    Attributes:
        text: The text answer (empty when it only called tools).
        tool_calls: The tools it asked to call.
        usage: Tokens used by the call.
        key_alias: Alias of the key that served the call, never the key.
    """

    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    usage: Usage = field(default_factory=Usage)
    key_alias: str | None = None


class LLMClient(Protocol):
    """The seam between the evaluation and a language model; one model per client."""

    def chat(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolDeclaration] = (),
        *,
        system: str | None = None,
    ) -> ChatResult:
        """Send the conversation and return the model's next turn.

        Args:
            messages: The conversation so far.
            tools: Tools the model may call.
            system: Optional system instruction.

        Returns:
            The text and/or tool calls, with the usage.
        """
        ...
