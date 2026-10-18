"""The Cursor: an opaque, stateless token for the next page of a Case search."""

import base64
import binascii
import json
from dataclasses import dataclass

from juris_bridge_mcp.domain.courts import DATAJUD_COURTS
from juris_bridge_mcp.domain.errors import ErrorCode, ToolFailure


def _invalid() -> ToolFailure:
    return ToolFailure(
        ErrorCode.INVALID_ARGUMENT,
        "The cursor is not valid.",
        source=None,
        retryable=False,
        hint="Pass next_cursor exactly as a previous search returned it.",
    )


@dataclass(frozen=True)
class Cursor:
    """Where a search stopped: the Court, the Source's sort position and the filters it ran with.

    `court` is the scope the search ran in: a Court alias, or `senado` for a legislation search,
    whose position is `(offset, 0)`.
    `filters_key` lets a later call notice that the filters changed under the same cursor.
    """

    court: str
    position: tuple[int | str, int | str]
    filters_key: str

    def encode(self) -> str:
        """Return the URL-safe, unpadded token."""
        body = {"c": self.court, "p": list(self.position), "f": self.filters_key}
        raw = json.dumps(body, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    @classmethod
    def decode(cls, token: str, scopes: tuple[str, ...] = DATAJUD_COURTS) -> "Cursor":
        """Parse a token, or raise `invalid_argument` for anything outside `scopes`."""
        try:
            body = json.loads(base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)))
            court, position, key = body["c"], body["p"], body["f"]
        except (ValueError, KeyError, TypeError, binascii.Error):
            raise _invalid() from None
        if (
            court not in scopes
            or not isinstance(key, str)
            or not isinstance(position, list)
            or len(position) != 2
            or any(isinstance(p, bool) or not isinstance(p, int | str) for p in position)
        ):
            raise _invalid()
        return cls(court=court, position=(position[0], position[1]), filters_key=key)
