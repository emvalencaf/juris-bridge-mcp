"""Key rotation: moving to the next key on daily exhaustion, scripted HTTP only."""

import json

import httpx
import pytest
from pydantic import SecretStr

from evals.llm import (
    AllKeysExhausted,
    FakeClock,
    GeminiClient,
    LLMError,
    Message,
    RateLimiter,
    RequestBudget,
    RotatingKeySource,
    SingleKeySource,
    key_source_from,
)
from evals.tests.test_llm_gemini import ASK, Upstream, ok, settings

SECRETS = ["secret-aaa", "secret-bbb", "secret-ccc"]


def _quota_429(quota_id):
    body = {
        "error": {
            "code": 429,
            "status": "RESOURCE_EXHAUSTED",
            "message": "You exceeded your current quota.",
            "details": [
                {
                    "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                    "violations": [{"quotaId": quota_id}],
                }
            ],
        }
    }
    return httpx.Response(429, json=body)


def daily_429():
    return _quota_429("GenerateRequestsPerDayPerProjectPerModel-FreeTier")


def minute_429():
    return _quota_429("GenerateRequestsPerMinutePerProjectPerModel-FreeTier")


def build(responses, keys, **over):
    s = settings(**over)
    clock = FakeClock()
    upstream = Upstream(responses)
    client = GeminiClient(
        "agent-m",
        keys,
        RateLimiter(s.requests_per_minute, s.tokens_per_minute, clock, clock.sleep),
        RequestBudget(100),
        s,
        clock.sleep,
        transport=httpx.MockTransport(upstream),
    )
    return client, upstream, clock


def rotating():
    return RotatingKeySource([SecretStr(s) for s in SECRETS])


def test_rotating_source_names_keys_by_position_and_moves_on_when_one_is_exhausted():
    keys = rotating()
    first = keys.current()
    assert first.alias == "key-1"

    keys.mark_exhausted(first)

    assert keys.current().alias == "key-2"


def test_rotating_source_raises_when_every_key_is_exhausted():
    keys = rotating()
    for _ in SECRETS:
        keys.mark_exhausted(keys.current())

    with pytest.raises(AllKeysExhausted) as raised:
        keys.current()

    assert isinstance(raised.value, LLMError)
    assert not any(s in str(raised.value) for s in SECRETS)


def test_a_daily_429_moves_the_call_to_the_next_key_without_waiting():
    client, upstream, clock = build([daily_429(), ok("done")], rotating())

    result = client.chat(ASK)

    assert result.text == "done"
    assert result.key_alias == "key-2"
    used = [r.headers["x-goog-api-key"] for r in upstream.requests]
    assert used == ["secret-aaa", "secret-bbb"]
    assert clock.sleeps == []


def test_a_per_minute_429_backs_off_and_keeps_the_same_key():
    client, upstream, clock = build([minute_429(), ok("done")], rotating())

    result = client.chat(ASK)

    assert result.key_alias == "key-1"
    assert len({r.headers["x-goog-api-key"] for r in upstream.requests}) == 1
    assert clock.sleeps[:1] == [2.0]


def test_the_exhausted_key_stays_skipped_by_later_calls():
    client, upstream, _ = build([daily_429(), ok(), ok()], rotating())

    client.chat(ASK)
    second = client.chat(ASK)

    assert second.key_alias == "key-2"
    assert upstream.requests[2].headers["x-goog-api-key"] == "secret-bbb"


def test_when_every_key_is_exhausted_the_call_raises_without_leaking_a_key():
    client, upstream, _ = build([daily_429()] * 3, rotating())

    with pytest.raises(AllKeysExhausted) as raised:
        client.chat(ASK)

    assert len(upstream.requests) == 3
    assert not any(s in str(raised.value) for s in SECRETS)


def test_rotation_does_not_spend_the_retry_allowance():
    client, _, _ = build([daily_429(), daily_429(), ok("done")], rotating(), max_retries=0)

    assert client.chat(ASK).text == "done"


def test_a_single_key_still_backs_off_on_any_429_as_before():
    keys = SingleKeySource(SecretStr(SECRETS[0]))
    client, upstream, clock = build([daily_429(), ok("done")], keys)

    result = client.chat(ASK)

    assert result.key_alias == "key-1"
    assert len(upstream.requests) == 2
    assert clock.sleeps[:1] == [2.0]


def test_rotation_is_off_by_default_and_one_key_gives_a_single_source():
    s = settings(gemini_api_keys=SecretStr("a,b"), gemini_api_key=SecretStr("c"))

    source = key_source_from(s)

    assert isinstance(source, SingleKeySource)
    assert source.current().secret.get_secret_value() == "a"


def test_rotation_opt_in_uses_every_key_given():
    s = settings(rotate_keys=True, gemini_api_keys=SecretStr("a, b"), gemini_api_key=SecretStr("c"))

    source = key_source_from(s)

    assert isinstance(source, RotatingKeySource)
    seen = []
    for _ in range(3):
        key = source.current()
        seen.append(key.secret.get_secret_value())
        source.mark_exhausted(key)
    assert seen == ["a", "b", "c"]


def test_opt_in_with_one_key_is_a_single_source():
    s = settings(rotate_keys=True, gemini_api_key=SecretStr("only"))

    assert isinstance(key_source_from(s), SingleKeySource)


def test_no_key_at_all_is_a_clear_error():
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        key_source_from(settings())


def test_the_request_body_never_carries_a_key():
    client, upstream, _ = build([ok()], rotating())

    client.chat([Message(role="user", text="q")])

    assert "secret-" not in json.dumps(json.loads(upstream.requests[0].content))
