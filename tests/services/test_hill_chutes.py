"""HTTP mocked: no Chutes keys, network calls or inference spend."""

import base64
import json
import sqlite3

import httpx
import pytest

from cadrecover.protocol import Artifact, PublicChallenge
from cadrecover.storage import db
from cadrecover.validator.hill.budget import BudgetExceeded
from cadrecover.validator.hill.chutes import (ChutesRunner, ChutesUnavailable, SYSTEM_PROMPT, SYSTEM_PROMPT_V1,
                                             HARNESS_VERSION)


MODEL = "google/gemma-4-31B-turbo-TEE"


def metadata(model_id=MODEL, modalities=None):
    return {"id": model_id, "input_modalities": modalities or ["text", "image"],
            "price": {"input": {"usd": .12}, "output": {"usd": .37}},
            "context_length": 131072, "max_output_length": 65536, "confidential_compute": True}


def public():
    return PublicChallenge(challenge_id="ch_test", family="flange", frame="bottom at z=0",
                           parameters=[], edit_rules=["holes follow the bolt circle"], critical_features=[],
                           drawing=Artifact(path="ch_test/drawing.png", sha256="0" * 64, media_type="image/png"))


def reply(content="```python\ndef build_part(overrides):\n    return None\n```", usage=None):
    return {"choices": [{"message": {"content": content}}],
            "usage": usage or {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}}


def runner(monkeypatch, post, *, model_records=None, **kwargs):
    monkeypatch.setenv("CHUTES_API_KEY", "test-only-dummy")
    calls = []

    def handle(request):
        calls.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={"data": model_records or [metadata()]})
        return post(request)

    con = db.connect(":memory:")
    client = httpx.Client(transport=httpx.MockTransport(handle))
    return ChutesRunner(con, http=client, **kwargs), calls, con


def test_good_reply_fixed_harness_image_and_exact_token_cost(monkeypatch):
    obj, calls, con = runner(monkeypatch, lambda req: httpx.Response(200, json=reply()))
    result = obj.generate(MODEL, public(), b"a PNG", "match")
    assert result.source.startswith("def build_part(overrides):")
    assert result.error is None and result.latency_s >= 0
    assert result.prompt_tokens == 100 and result.completion_tokens == 50
    assert result.cost_usd == pytest.approx((100 * .12 + 50 * .37) / 1_000_000)
    request = calls[-1]
    payload = json.loads(request.content)
    assert request.headers["authorization"] == "Bearer test-only-dummy"
    assert payload["messages"][0]["content"] == SYSTEM_PROMPT
    image = payload["messages"][1]["content"][1]["image_url"]["url"]
    assert base64.b64decode(image.split(",")[1]) == b"a PNG"
    assert "holes follow the bolt circle" in payload["messages"][1]["content"][0]["text"]
    assert con.execute("SELECT state FROM hill_spend").fetchone()[0] == "charged"


@pytest.mark.parametrize("content", ["plain text", "```python\nx=1\n```\nprose",
                                     "```python\nx=1\n```\n```python\ny=2\n```", "```python\n\n```", None])
def test_invalid_output_is_charged_miner_failure(monkeypatch, content):
    obj, calls, con = runner(monkeypatch, lambda req: httpx.Response(200, json=reply(content)))
    result = obj.generate(MODEL, public(), b"png", "match")
    assert result.source is None and result.error
    assert obj.budget.totals() > 0
    assert len([r for r in calls if r.method == "POST"]) == 1


def test_timeout_only_one_retry_and_both_unknown_charges_persist(monkeypatch):
    def timeout(req):
        raise httpx.ReadTimeout("never expose this detail", request=req)

    obj, calls, con = runner(monkeypatch, timeout)
    with pytest.raises(ChutesUnavailable, match="one retry"):
        obj.generate(MODEL, public(), b"png", "match")
    assert len([r for r in calls if r.method == "POST"]) == 2
    assert [r[0] for r in con.execute("SELECT state FROM hill_spend")] == ["unknown", "unknown"]
    assert obj.budget.totals() == pytest.approx(2 * (.12 * 131072 + .37 * 4096) / 1_000_000)


def test_retry_success_accounts_for_unknown_first_attempt(monkeypatch):
    attempts = 0

    def respond(req):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ConnectError("private details", request=req)
        return httpx.Response(200, json=reply())

    obj, calls, con = runner(monkeypatch, respond)
    result = obj.generate(MODEL, public(), b"png", "match")
    assert result.source
    assert result.cost_usd == obj.budget.totals()


def test_budget_refusal_never_sends_post_and_propagates(monkeypatch):
    obj, calls, con = runner(monkeypatch, lambda req: pytest.fail("Must not send paid request"), total_cap=.001)
    with pytest.raises(BudgetExceeded):
        obj.generate(MODEL, public(), b"png", "match")
    assert all(r.method == "GET" for r in calls)
    assert obj.budget.totals() == 0


def test_retry_has_independent_budget_check(monkeypatch):
    def timeout(req):
        raise httpx.ReadTimeout("detail", request=req)

    obj, calls, con = runner(monkeypatch, timeout, match_cap=.02)
    with pytest.raises(BudgetExceeded):
        obj.generate(MODEL, public(), b"png", "match")
    assert len([r for r in calls if r.method == "POST"]) == 1
    assert obj.budget.totals() > 0


def test_http_error_not_retried_and_response_body_is_not_exposed(monkeypatch):
    obj, calls, con = runner(monkeypatch, lambda req: httpx.Response(429, text="potential private details"))
    with pytest.raises(ChutesUnavailable, match="HTTP 429") as exc:
        obj.generate(MODEL, public(), b"png", "match")
    assert "private details" not in str(exc.value)
    assert len([r for r in calls if r.method == "POST"]) == 1
    assert con.execute("SELECT state FROM hill_spend").fetchone()[0] == "unknown"


@pytest.mark.parametrize("usage", [{"prompt_tokens": -1, "completion_tokens": 1},
                                   {"prompt_tokens": 1, "completion_tokens": 4097},
                                   {"prompt_tokens": 131071, "completion_tokens": 2},
                                   {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 99},
                                   {"prompt_tokens": True, "completion_tokens": 1}])
def test_invalid_usage_is_conservatively_reserved(monkeypatch, usage):
    obj, calls, con = runner(monkeypatch, lambda req: httpx.Response(200, json=reply(usage=usage)))
    with pytest.raises(ChutesUnavailable, match="usage"):
        obj.generate(MODEL, public(), b"png", "match")
    assert tuple(con.execute("SELECT cost_usd = reserved_usd, state FROM hill_spend").fetchone()) == (1, "unknown")


def test_catalog_excludes_nonvision_kimi_k3_and_unpriced(monkeypatch):
    records = [metadata("moonshotai/Kimi-K3-TEE"), metadata("text-only", ["text"]),
               {"id": "unpriced", "input_modalities": ["image"]}, metadata("Qwen/vision"), metadata()]
    obj, calls, con = runner(monkeypatch, lambda req: pytest.fail("no POST"), model_records=records)
    assert [m.id for m in obj.catalog()] == [MODEL, "Qwen/vision"]
    assert obj.budget.totals() == 0


def test_missing_key_fails_before_network(monkeypatch):
    obj, calls, con = runner(monkeypatch, lambda req: pytest.fail("no POST"))
    monkeypatch.delenv("CHUTES_API_KEY")
    with pytest.raises(ChutesUnavailable, match="not configured"):
        obj.generate(MODEL, public(), b"png", "match")
    assert calls == []


def test_harness_version_selects_the_fixed_prompt_and_unknown_is_refused(monkeypatch):
    obj, calls, con = runner(monkeypatch, lambda req: httpx.Response(200, json=reply()))
    obj.generate(MODEL, public(), b"a PNG", "match", 1)
    assert json.loads(calls[-1].content)["messages"][0]["content"] == SYSTEM_PROMPT_V1
    obj.generate(MODEL, public(), b"a PNG", "match", HARNESS_VERSION)
    assert json.loads(calls[-1].content)["messages"][0]["content"] == SYSTEM_PROMPT
    assert SYSTEM_PROMPT.startswith(SYSTEM_PROMPT_V1) and "Cylinder(radius, height" in SYSTEM_PROMPT
    posts = sum(1 for r in calls if r.method == "POST")
    with pytest.raises(ChutesUnavailable):
        obj.generate(MODEL, public(), b"a PNG", "match", 99)
    assert sum(1 for r in calls if r.method == "POST") == posts

def test_provider_receipt_correlates_usage_without_secrets_or_drawing(monkeypatch):
    data={**reply(),"id":"provider-response-123","model":MODEL}
    obj,calls,con=runner(monkeypatch,lambda req:httpx.Response(
        200,json=data,headers={"x-request-id":"provider-request-456"}))
    obj.generate(MODEL,public(),b"secret-png-bytes","match")
    row=con.execute("SELECT payload FROM events WHERE kind='hill.provider_response'").fetchone()
    payload=json.loads(row[0])
    assert payload["response_id"]=="provider-response-123"
    assert payload["request_id"]=="provider-request-456"
    assert payload["prompt_tokens"]==100 and payload["completion_tokens"]==50
    assert payload["status_code"]==200 and payload["requested_model"]==MODEL
    assert con.execute("SELECT id FROM hill_spend").fetchone()[0]==payload["spend_id"]
    assert "test-only-dummy" not in row[0] and "secret-png-bytes" not in row[0]
    assert "messages" not in payload and "Authorization" not in row[0]
