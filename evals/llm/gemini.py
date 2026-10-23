"""The Gemini implementation of `LLMClient`, over the REST API with httpx."""

import json
from collections.abc import Callable, Sequence
from typing import Any

import httpx
from pydantic import SecretStr

from evals.llm.client import ChatResult, Message, ToolCall, ToolDeclaration, Usage
from evals.llm.errors import GeminiAPIError, RateLimitRetriesExhausted
from evals.llm.keys import KeySource
from evals.llm.limits import RateLimiter, RequestBudget
from evals.llm.settings import EvalLLMSettings

RETRYABLE_STATUSES = frozenset({429, 503})
CHARS_PER_TOKEN = 4


class GeminiClient:
    """Calls `generateContent` of one Gemini model, within the rate limits and the run cap.

    Waits on requests and tokens per minute before each request, retries 429 (and 503) with
    exponential backoff (no retry header is documented), and counts every attempt against the
    shared `RequestBudget`. The key goes in a header, never in the URL, and never in an error.

    Args:
        model: The model name (from settings).
        keys: Chooses the key for each request.
        limiter: Waits on requests and tokens per minute.
        budget: The cap of requests per run, shared by the clients of a run.
        settings: Supplies the base URL, timeout and retry/backoff values.
        sleep: Waits for the given seconds (injectable, used for backoff).
        transport: httpx transport (injectable; tests script it).
    """

    def __init__(
        self,
        model: str,
        keys: KeySource,
        limiter: RateLimiter,
        budget: RequestBudget,
        settings: EvalLLMSettings,
        sleep: Callable[[float], None],
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._model = model
        self._keys = keys
        self._limiter = limiter
        self._budget = budget
        self._settings = settings
        self._sleep = sleep
        self._http = httpx.Client(
            base_url=settings.base_url.rstrip("/"),
            timeout=settings.timeout_seconds,
            transport=transport,
        )

    def __repr__(self) -> str:
        return f"GeminiClient(model={self._model!r})"

    def chat(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolDeclaration] = (),
        *,
        system: str | None = None,
    ) -> ChatResult:
        """Send the conversation to Gemini and return its next turn.

        Raises:
            RequestCapReached: When the run's cap of requests is used up.
            RateLimitRetriesExhausted: When every retry met a 429 or 503.
            GeminiAPIError: On any other failure.
        """
        body = _build_body(messages, tools, system)
        estimate = len(json.dumps(body)) // CHARS_PER_TOKEN + 1
        delay = self._settings.backoff_base_seconds
        attempts = self._settings.max_retries + 1
        attempt = 0
        while attempt < attempts:
            self._budget.take()
            ticket = self._limiter.acquire(estimate)
            key = self._keys.current()
            try:
                response = self._http.post(
                    f"/models/{self._model}:generateContent",
                    json=body,
                    headers={"x-goog-api-key": key.secret.get_secret_value()},
                )
            except httpx.HTTPError as error:
                # An httpx message may name the URL; keep only the error type.
                raise GeminiAPIError(0, f"transport failure ({type(error).__name__})") from None
            if response.status_code in RETRYABLE_STATUSES:
                if response.status_code == 429 and _is_daily_quota(response):
                    self._keys.mark_exhausted(key)
                    # Raises AllKeysExhausted when rotation has no key left.
                    if self._keys.current().alias != key.alias:
                        continue  # moved to the next key: no wait, no retry spent
                attempt += 1
                if attempt < attempts:
                    self._sleep(delay)
                    delay = min(delay * 2, self._settings.backoff_max_seconds)
                continue
            if response.status_code != 200:
                raise GeminiAPIError(response.status_code, _error_message(response, key.secret))
            result = _parse(response.json(), key.alias)
            self._limiter.settle(ticket, result.usage.total_tokens)
            return result
        raise RateLimitRetriesExhausted(f"{attempts} attempts for {self._model} all met 429 or 503")


def _is_daily_quota(response: httpx.Response) -> bool:
    """Whether a 429 says the daily quota is spent (not a per-minute limit).

    Assumption (research note, section 3): the API maps 429 to `quota_exceeded` (daily) and
    `rate_limit_exceeded` (per minute), but the live body shape is not documented. We treat a
    429 as daily when its body names a `...PerDay...` quota id or says "per day"/"daily".
    Anything else counts as per-minute and is only retried with backoff.
    """
    text = response.text.lower()
    return "perday" in text or "per day" in text or "daily" in text


def _build_body(
    messages: Sequence[Message], tools: Sequence[ToolDeclaration], system: str | None
) -> dict[str, Any]:
    body: dict[str, Any] = {"contents": [_content(m) for m in messages]}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    if tools:
        body["tools"] = [{"functionDeclarations": [_declaration(t) for t in tools]}]
    return body


def _declaration(tool: ToolDeclaration) -> dict[str, Any]:
    declaration: dict[str, Any] = {"name": tool.name, "description": tool.description}
    if tool.parameters:
        declaration["parameters"] = tool.parameters
    return declaration


def _content(message: Message) -> dict[str, Any]:
    if message.role == "tool":
        response = {"name": message.tool_name, "response": {"result": message.text}}
        return {"role": "user", "parts": [{"functionResponse": response}]}
    parts: list[dict[str, Any]] = []
    if message.text:
        parts.append({"text": message.text})
    for call in message.tool_calls:
        part: dict[str, Any] = {"functionCall": {"name": call.name, "args": call.arguments}}
        if call.signature:
            part["thoughtSignature"] = call.signature
        parts.append(part)
    return {"role": "model" if message.role == "assistant" else "user", "parts": parts}


def _parse(payload: dict[str, Any], key_alias: str) -> ChatResult:
    candidates = payload.get("candidates") or [{}]
    parts = (candidates[0].get("content") or {}).get("parts") or []
    text = "".join(p["text"] for p in parts if "text" in p and not p.get("thought"))
    calls = tuple(
        ToolCall(
            name=p["functionCall"]["name"],
            arguments=dict(p["functionCall"].get("args") or {}),
            signature=p.get("thoughtSignature"),
        )
        for p in parts
        if "functionCall" in p
    )
    meta = payload.get("usageMetadata") or {}
    input_tokens = int(meta.get("promptTokenCount", 0))
    total = int(meta.get("totalTokenCount", 0))
    output_tokens = max(total - input_tokens, int(meta.get("candidatesTokenCount", 0)))
    return ChatResult(
        text=text,
        tool_calls=calls,
        usage=Usage(input_tokens=input_tokens, output_tokens=output_tokens),
        key_alias=key_alias,
    )


def _error_message(response: httpx.Response, secret: SecretStr) -> str:
    try:
        message = str(response.json()["error"]["message"])
    except (ValueError, KeyError, TypeError):
        message = "no error message"
    return message.replace(secret.get_secret_value(), "[redacted]")[:300]
