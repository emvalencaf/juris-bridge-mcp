"""The closed set of Error codes and the MCP error shape every tool failure uses."""

import json
import math
from enum import StrEnum
from typing import Any

from fastmcp.exceptions import ToolError


class ErrorCode(StrEnum):
    """Why a call failed; an agent branches on this value."""

    INVALID_ARGUMENT = "invalid_argument"
    NOT_FOUND = "not_found"
    NOT_COVERED = "not_covered"
    RATE_LIMITED = "rate_limited"
    SOURCE_UNAVAILABLE = "source_unavailable"
    SOURCE_AUTH_FAILED = "source_auth_failed"
    SOURCE_CHANGED = "source_changed"
    SOURCE_BLOCKED = "source_blocked"


class ToolFailure(Exception):  # noqa: N818 - domain term, not a generic error suffix
    """A tool failure carrying an Error code; adapters turn it into an MCP error."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        source: str | None,
        retryable: bool,
        retry_after_seconds: int | None = None,
        hint: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.source = source
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds
        self.hint = hint

    def payload(self) -> dict[str, Any]:
        """Return `{code, message, source, retryable, retry_after_seconds?, hint?}`."""
        body: dict[str, Any] = {
            "code": self.code.value,
            "message": self.message,
            "source": self.source,
            "retryable": self.retryable,
        }
        if self.retry_after_seconds is not None:
            body["retry_after_seconds"] = self.retry_after_seconds
        if self.hint is not None:
            body["hint"] = self.hint
        return body

    def to_json(self) -> str:
        """Serialize the payload as the text of the MCP error."""
        return json.dumps(self.payload(), ensure_ascii=False)


def to_tool_error(failure: ToolFailure) -> ToolError:
    """Convert a failure into the MCP error (`isError: true`) a tool raises."""
    return ToolError(failure.to_json())


def rate_limited(source: str, message: str, *, retry_after_seconds: float) -> ToolFailure:
    """Build the retryable `rate_limited` failure, rounding the wait up to whole seconds."""
    return ToolFailure(
        ErrorCode.RATE_LIMITED,
        message,
        source=source,
        retryable=True,
        retry_after_seconds=math.ceil(retry_after_seconds),
        hint="Wait retry_after_seconds before calling again.",
    )


def invalid_argument(message: str, hint: str | None = None) -> ToolFailure:
    """Build the non-retryable `invalid_argument` failure, which names no Source."""
    return ToolFailure(ErrorCode.INVALID_ARGUMENT, message, source=None, retryable=False, hint=hint)


def not_found(source: str, message: str, hint: str) -> ToolFailure:
    """Build the non-retryable `not_found` failure, with a hint on how to find the item."""
    return source_failure(source, ErrorCode.NOT_FOUND, message, retryable=False, hint=hint)


def source_failure(
    source: str, code: ErrorCode, message: str, *, retryable: bool, hint: str | None = None
) -> ToolFailure:
    """Build a failure attributed to `source`."""
    return ToolFailure(code, message, source=source, retryable=retryable, hint=hint)


def source_changed(source: str, name: str, detail: str) -> ToolFailure:
    """Build the `source_changed` failure for an answer `name` gave in an unknown shape."""
    return source_failure(
        source,
        ErrorCode.SOURCE_CHANGED,
        f"{name} answered in a shape this server does not understand ({detail}).",
        retryable=False,
        hint="Do not trust partial data; report the problem to the operator.",
    )
