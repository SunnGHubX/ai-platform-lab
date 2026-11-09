import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import RateLimiter, Settings, create_app

KEY = "test-key-1234"
AUTH = {"Authorization": f"Bearer {KEY}"}
CHAT = {"model": "qwen", "messages": [{"role": "user", "content": "hi"}]}


def upstream(status: int = 200, body: dict | None = None, exc: Exception | None = None, seen: list | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        if exc:
            raise exc
        if request.url.path == "/health":
            return httpx.Response(status)
        return httpx.Response(status, json=body or {"choices": [{"message": {"content": "hello"}}]})

    return httpx.MockTransport(handler)


def client(transport=None, **overrides) -> TestClient:
    settings = Settings(api_keys=frozenset({KEY}), **overrides)
    return TestClient(create_app(settings, transport=transport or upstream()))


# ---------------------------------------------------------------- config / startup
def test_refuses_to_start_without_keys():
    with pytest.raises(ValueError, match="API_KEYS"):
        create_app(Settings(api_keys=frozenset()))


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("API_KEYS", " a , b ,")
    monkeypatch.setenv("MAX_TOKENS_CAP", "256")
    s = Settings.from_env()
    assert s.api_keys == {"a", "b"} and s.max_tokens_cap == 256


# ---------------------------------------------------------------- health
def test_healthz():
    with client() as c:
        assert c.get("/healthz").json() == {"status": "ok"}


def test_readyz_reflects_upstream():
    with client(upstream(200)) as c:
        assert c.get("/readyz").status_code == 200
    with client(upstream(exc=httpx.ConnectError("down"))) as c:
        assert c.get("/readyz").status_code == 503


# ---------------------------------------------------------------- auth
@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer wrong"}, {"Authorization": f"Basic {KEY}"}])
def test_rejects_bad_credentials(headers):
    with client() as c:
        assert c.post("/v1/chat/completions", json=CHAT, headers=headers).status_code == 401


def test_auth_can_be_disabled_for_local_dev():
    with TestClient(create_app(Settings(auth_disabled=True), transport=upstream())) as c:
        assert c.post("/v1/chat/completions", json=CHAT).status_code == 200


# ---------------------------------------------------------------- proxying
def test_proxies_and_applies_default_max_tokens():
    seen: list[httpx.Request] = []
    with client(upstream(seen=seen), max_tokens_cap=128) as c:
        r = c.post("/v1/chat/completions", json={**CHAT, "temperature": 0.2}, headers=AUTH)
    assert r.status_code == 200
    assert r.json()["choices"][0]["message"]["content"] == "hello"
    sent = httpx.Response(200, content=seen[0].content).json()
    assert sent["max_tokens"] == 128 and sent["temperature"] == 0.2  # cap applied, extras passed through


def test_upstream_5xx_becomes_502():
    with client(upstream(500)) as c:
        assert c.post("/v1/chat/completions", json=CHAT, headers=AUTH).status_code == 502


def test_upstream_4xx_passes_through():
    with client(upstream(400, {"error": "bad model"})) as c:
        assert c.post("/v1/chat/completions", json=CHAT, headers=AUTH).status_code == 400


def test_upstream_timeout_becomes_504():
    with client(upstream(exc=httpx.ReadTimeout("slow"))) as c:
        assert c.post("/v1/chat/completions", json=CHAT, headers=AUTH).status_code == 504


def test_upstream_unreachable_becomes_502():
    with client(upstream(exc=httpx.ConnectError("refused"))) as c:
        assert c.post("/v1/chat/completions", json=CHAT, headers=AUTH).status_code == 502


# ---------------------------------------------------------------- input validation
@pytest.mark.parametrize(
    "body",
    [
        {"model": "qwen", "messages": []},
        {"model": "", "messages": CHAT["messages"]},
        {"model": "qwen", "messages": [{"role": "hacker", "content": "x"}]},
        {**CHAT, "max_tokens": 0},
    ],
)
def test_rejects_invalid_requests(body):
    with client() as c:
        assert c.post("/v1/chat/completions", json=body, headers=AUTH).status_code == 422


def test_max_tokens_cap_enforced():
    with client(max_tokens_cap=100) as c:
        assert c.post("/v1/chat/completions", json={**CHAT, "max_tokens": 101}, headers=AUTH).status_code == 422


def test_streaming_rejected():
    with client() as c:
        assert c.post("/v1/chat/completions", json={**CHAT, "stream": True}, headers=AUTH).status_code == 400


# ---------------------------------------------------------------- rate limiting
def test_rate_limit_returns_429_with_retry_after():
    with client(rate_limit_rpm=2) as c:
        codes = [c.post("/v1/chat/completions", json=CHAT, headers=AUTH).status_code for _ in range(3)]
        assert codes == [200, 200, 429]
        r = c.post("/v1/chat/completions", json=CHAT, headers=AUTH)
        assert r.headers["retry-after"] == "60"


def test_rate_limiter_resets_each_minute():
    now = [0.0]
    limiter = RateLimiter(rpm=1, clock=lambda: now[0])
    assert limiter.allow("k") and not limiter.allow("k")
    now[0] = 61.0
    assert limiter.allow("k")


def test_rate_limit_is_per_key():
    limiter = RateLimiter(rpm=1, clock=lambda: 0.0)
    assert limiter.allow("a") and limiter.allow("b")


# ---------------------------------------------------------------- SLI metrics (the SLOs depend on these names)
def test_metrics_record_codes_and_latency():
    with client(upstream(500)) as c:
        c.post("/v1/chat/completions", json=CHAT, headers=AUTH)  # 502
        c.post("/v1/chat/completions", json=CHAT)  # 401
        c.get("/healthz")  # not metered
        text = c.get("/metrics").text
    assert 'gateway_requests_total{code="502",route="/v1/chat/completions"} 1.0' in text
    assert 'gateway_requests_total{code="401",route="/v1/chat/completions"} 1.0' in text
    assert 'gateway_request_duration_seconds_bucket{le="2.5",route="/v1/chat/completions"}' in text
    assert "/healthz" not in text
