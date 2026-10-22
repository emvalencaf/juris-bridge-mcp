"""Test doubles: a scripted client and a fake clock. No network, no waiting."""

from collections.abc import Sequence

from evals.llm.client import ChatResult, Message, ToolDeclaration


class ScriptedLLMClient:
    """An `LLMClient` that answers from a script, in order, and records what it was sent.

    A script item that is an exception is raised instead of returned.
    """

    def __init__(self, script: Sequence[ChatResult | Exception]) -> None:
        self._script = list(script)
        self.calls: list[tuple[list[Message], list[ToolDeclaration], str | None]] = []

    def chat(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolDeclaration] = (),
        *,
        system: str | None = None,
    ) -> ChatResult:
        """Return (or raise) the next scripted item."""
        self.calls.append((list(messages), list(tools), system))
        if not self._script:
            raise AssertionError("the scripted client ran out of answers")
        item = self._script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeClock:
    """A clock whose `sleep` only moves time forward, so rate-limit waits are instant."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        """Advance the clock instead of waiting."""
        self.sleeps.append(seconds)
        self.now += seconds
