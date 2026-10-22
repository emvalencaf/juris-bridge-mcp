"""ASGI middleware that requires a Bearer API key on every HTTP request."""

import hashlib
import hmac

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from juris_bridge_mcp.adapters import wide_event


class BearerAuthMiddleware:
    """Answer 401 unless `Authorization: Bearer <key>` matches a configured key."""

    def __init__(self, app: ASGIApp, keys: tuple[str, ...]) -> None:
        self.app = app
        self._keys = tuple(k.encode() for k in keys)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        token = self._authorized_token(scope)
        if token is not None:
            wide_event.set_caller(hashlib.sha256(token).hexdigest()[:8])
            await self.app(scope, receive, send)
            return
        response = JSONResponse(
            {"error": "unauthorized"}, status_code=401, headers={"WWW-Authenticate": "Bearer"}
        )
        await response(scope, receive, send)

    def _authorized_token(self, scope: Scope) -> bytes | None:
        header = dict(scope["headers"]).get(b"authorization", b"")
        scheme, _, token = header.partition(b" ")
        if scheme.lower() != b"bearer" or not token:
            return None
        # Compare against every key so timing does not reveal which one matched.
        matches = [hmac.compare_digest(token, key) for key in self._keys]
        return token if any(matches) else None
