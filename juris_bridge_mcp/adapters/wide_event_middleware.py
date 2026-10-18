"""ASGI middleware that emits exactly one wide event per HTTP request (ADR 0004)."""

import json
import logging
import time
import uuid
from collections.abc import Mapping
from typing import Any

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from juris_bridge_mcp.adapters import wide_event
from juris_bridge_mcp.adapters.wide_event import WideEvent

_REQUEST_ID_HEADER = "x-amzn-requestid"
_MAX_BODY_BYTES = 64 * 1024
_MAX_TOOL_NAME = 64
_logger = logging.getLogger(wide_event.LOGGER_NAME)


class WideEventMiddleware:
    """Build the event around the app and emit it in `finally`, whatever happens."""

    def __init__(self, app: ASGIApp, environment: Mapping[str, Any] | None = None) -> None:
        self.app = app
        self._environment = dict(environment or {})

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        event = WideEvent(self._environment, headers.get(_REQUEST_ID_HEADER) or str(uuid.uuid4()))
        token = wide_event.start(event)
        wide_event.annotate_request(method=scope["method"], user_agent=headers.get("user-agent"))
        started = time.perf_counter()
        status = 500
        body = bytearray()

        async def capture_receive() -> Message:
            message = await receive()
            if message["type"] == "http.request" and len(body) <= _MAX_BODY_BYTES:
                body.extend(message.get("body", b""))
            return message

        async def capture_send(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, capture_receive, capture_send)
        finally:
            self._annotate_mcp(scope, bytes(body))
            record = event.finish(status=status, duration_ms=(time.perf_counter() - started) * 1000)
            _logger.log(logging.ERROR if status >= 500 else logging.INFO, json.dumps(record))
            wide_event.stop(token)

    @staticmethod
    def _annotate_mcp(scope: Scope, body: bytes) -> None:
        if scope["method"] != "POST" or not body or len(body) > _MAX_BODY_BYTES:
            return
        try:
            message = json.loads(body)
        except ValueError:
            return
        if not isinstance(message, dict):
            return
        method = message.get("method")
        method = method if isinstance(method, str) else None
        tool = None
        if method == "tools/call":
            params = message.get("params")
            name = params.get("name") if isinstance(params, dict) else None
            tool = name[:_MAX_TOOL_NAME] if isinstance(name, str) else None
        wide_event.annotate_mcp(method=method, tool=tool)
