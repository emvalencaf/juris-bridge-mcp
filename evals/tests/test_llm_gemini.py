"""The Gemini client against a scripted HTTP transport; the Gemini API is never called."""

import json

import httpx
import pytest
from pydantic import SecretStr

from evals.llm import (
    EvalLLMSettings,
    FakeClock,
    GeminiAPIError,
    GeminiClient,
    Message,
    RateLimiter,
    RateLimitRetriesExhausted,
    RequestBudget,
    RequestCapReached,
    ScriptedLLMClient,
    SingleKeySource,
    ToolCall,
    ToolDeclaration,
)

SECRET = "sk-test-very-secret"  # noqa: S105


def settings(**over):
    values = {
        "agent_model": "agent-m",
        "judge_model": "judge-m",
        "calibration_model": "cal-m",
        "requests_per_minute": 15,
        "tokens_per_minute": 250_000,
        "requests_per_day": 500,
        "max_requests_per_run": 100,
        "max_retries": 3,
    }
    return EvalLLMSettings(_env_file=None, **{**values, **over})


def ok(text="hi", calls=(), prompt=10, total=15):
    parts = [{"text": text}] if text else []
    parts += [{"functionCall": {"name": n, "args": a}} for n, a in calls]
    return httpx.Response(
        200,
        json={
            "candidates": [{"content": {"role": "model", "parts": parts}}],
            "usageMetadata": {"promptTokenCount": prompt, "totalTokenCount": total},
        },
    )


class Upstream:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request):
        self.requests.append(request)
        return self.responses.pop(0)


def build(responses, *, cap=100, **over):
    s = settings(**over)
    clock = FakeClock()
    upstream = Upstream(responses)
    client = GeminiClient(
        "agent-m",
        SingleKeySource(SecretStr(SECRET)),
        RateLimiter(s.requests_per_minute, s.tokens_per_minute, clock, clock.sleep),
        RequestBudget(cap),
        s,
        clock.sleep,
        transport=httpx.MockTransport(upstream),
    )
    return client, upstream, clock


ASK = [Message(role="user", text="q")]


def test_a_text_answer_is_returned_with_usage_and_the_key_alias():
    client, upstream, _ = build([ok("answer", prompt=10, total=25)])

    result = client.chat(ASK, system="be brief")

    assert result.text == "answer"
    assert (result.usage.input_tokens, result.usage.output_tokens) == (10, 15)
    assert result.key_alias == "key-1"
    request = upstream.requests[0]
    assert request.url.path.endswith("/models/agent-m:generateContent")
    assert json.loads(request.content)["systemInstruction"]["parts"][0]["text"] == "be brief"


def test_tools_are_declared_and_calls_come_back():
    client, upstream, _ = build([ok("", calls=[("get_x", {"a": 1})])])
    tool = ToolDeclaration("get_x", "gets x", {"type": "object", "properties": {}})

    result = client.chat(ASK, [tool])

    assert result.tool_calls == (ToolCall("get_x", {"a": 1}),)
    declared = json.loads(upstream.requests[0].content)["tools"][0]["functionDeclarations"]
    assert declared[0]["name"] == "get_x"


def test_tool_results_and_earlier_calls_are_sent_back():
    client, upstream, _ = build([ok()])
    history = [
        *ASK,
        Message(role="assistant", tool_calls=(ToolCall("get_x", {"a": 1}, signature="sig"),)),
        Message(role="tool", text="result", tool_name="get_x"),
    ]

    client.chat(history)

    contents = json.loads(upstream.requests[0].content)["contents"]
    assert contents[1]["role"] == "model"
    assert contents[1]["parts"][0]["thoughtSignature"] == "sig"
    assert contents[2]["parts"][0]["functionResponse"]["name"] == "get_x"


def test_a_429_is_retried_with_exponential_backoff_and_does_not_abort():
    client, upstream, clock = build([httpx.Response(429), httpx.Response(429), ok("done")])

    result = client.chat(ASK)

    assert result.text == "done"
    assert len(upstream.requests) == 3
    assert clock.sleeps[:2] == [2.0, 4.0]


def test_backoff_is_capped():
    client, _, clock = build(
        [httpx.Response(429)] * 3 + [ok()], backoff_base_seconds=40.0, backoff_max_seconds=60.0
    )

    client.chat(ASK)

    assert clock.sleeps[:3] == [40.0, 60.0, 60.0]


def test_retries_run_out_with_a_clear_error():
    client, upstream, _ = build([httpx.Response(429)] * 4)

    with pytest.raises(RateLimitRetriesExhausted):
        client.chat(ASK)
    assert len(upstream.requests) == 4


def test_the_run_stops_at_the_request_cap():
    client, upstream, _ = build([ok(), ok()], cap=1)
    client.chat(ASK)

    with pytest.raises(RequestCapReached):
        client.chat(ASK)
    assert len(upstream.requests) == 1


def test_retried_attempts_count_against_the_cap():
    client, upstream, _ = build([httpx.Response(429)] * 5, cap=2)

    with pytest.raises(RequestCapReached):
        client.chat(ASK)
    assert len(upstream.requests) == 2


def test_the_client_waits_on_requests_per_minute():
    client, _, clock = build([ok(), ok(), ok()], requests_per_minute=2)

    for _ in range(3):
        client.chat(ASK)

    assert sum(clock.sleeps) >= 59.0


def test_the_client_waits_on_tokens_per_minute():
    client, _, clock = build([ok(total=999), ok()], tokens_per_minute=1000)

    client.chat(ASK)
    client.chat(ASK)

    assert sum(clock.sleeps) >= 59.0


def test_other_failures_raise_without_the_key():
    body = {"error": {"message": f"bad key {SECRET}"}}
    client, _, _ = build([httpx.Response(400, json=body)])

    with pytest.raises(GeminiAPIError) as raised:
        client.chat(ASK)

    assert raised.value.status_code == 400
    assert SECRET not in str(raised.value)


def test_a_transport_failure_does_not_leak_the_key_or_the_url():
    def boom(request):
        raise httpx.ConnectError(f"cannot reach {request.url} with {SECRET}")

    s = settings()
    clock = FakeClock()
    client = GeminiClient(
        "agent-m",
        SingleKeySource(SecretStr(SECRET)),
        RateLimiter(15, 250_000, clock, clock.sleep),
        RequestBudget(5),
        s,
        clock.sleep,
        transport=httpx.MockTransport(boom),
    )

    with pytest.raises(GeminiAPIError) as raised:
        client.chat(ASK)

    assert SECRET not in str(raised.value)
    assert SECRET not in repr(raised.value.__cause__)


def test_the_key_is_sent_in_a_header_and_never_shown():
    client, upstream, _ = build([ok()])

    client.chat(ASK)

    request = upstream.requests[0]
    assert request.headers["x-goog-api-key"] == SECRET
    assert SECRET not in str(request.url)
    assert SECRET not in repr(client)
    assert SECRET not in repr(SingleKeySource(SecretStr(SECRET)).current())


def test_settings_read_the_environment_and_never_show_the_keys(monkeypatch):
    for name, value in {
        "EVALS_AGENT_MODEL": "a",
        "EVALS_JUDGE_MODEL": "j",
        "EVALS_CALIBRATION_MODEL": "c",
        "EVALS_REQUESTS_PER_MINUTE": "15",
        "EVALS_TOKENS_PER_MINUTE": "250000",
        "EVALS_REQUESTS_PER_DAY": "500",
        "EVALS_MAX_REQUESTS_PER_RUN": "800",
        "GEMINI_API_KEYS": "k1, k2",
        "GEMINI_API_KEY": "k0",
    }.items():
        monkeypatch.setenv(name, value)

    loaded = EvalLLMSettings(_env_file=None)

    assert loaded.agent_model == "a"
    assert loaded.request_cap == 500
    assert [k.get_secret_value() for k in loaded.api_keys()] == ["k1", "k2", "k0"]
    assert "k1" not in repr(loaded)


def test_the_scripted_client_answers_in_order_and_records_calls():
    from evals.llm import ChatResult

    fake = ScriptedLLMClient([ChatResult(text="a"), RuntimeError("boom")])

    assert fake.chat(ASK).text == "a"
    with pytest.raises(RuntimeError):
        fake.chat(ASK)
    assert len(fake.calls) == 2
