"""ASGI middleware that requires a Bearer API key on every HTTP request."""

import hmac

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


class BearerAuthMiddleware:
    """Answer 401 unless `Authorization: Bearer <key>` matches a configured key."""

    def __init__(self, app: ASGIApp, keys: tuple[str, ...]) -> None:
        self.app = app
        self._keys = tuple(k.encode() for k in keys)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or self._authorized(scope):
            await self.app(scope, receive, send)
            return
        response = JSONResponse(
            {"error": "unauthorized"}, status_code=401, headers={"WWW-Authenticate": "Bearer"}
        )
        await response(scope, receive, send)

    def _authorized(self, scope: Scope) -> bool:
        header = dict(scope["headers"]).get(b"authorization", b"")
        scheme, _, token = header.partition(b" ")
        if scheme.lower() != b"bearer" or not token:
            return False
        # Compare against every key so timing does not reveal which one matched.
        matches = [hmac.compare_digest(token, key) for key in self._keys]
        return any(matches)
