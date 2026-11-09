"""inference-gateway: a thin, secure front door for OpenAI-compatible model servers (vLLM, Triton).

Responsibilities kept deliberately small:
  * authenticate callers (API keys)            -> 401
  * protect GPUs from abuse (rate limit, caps)  -> 429 / 422
  * proxy to the model server                   -> 502/504 on upstream failure
  * emit the SLIs the SLOs are defined on       -> gateway_requests_total, gateway_request_duration_seconds
"""
from __future__ import annotations

import hmac
import os
import time
from collections import defaultdict
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram, generate_latest
from pydantic import BaseModel, ConfigDict, Field

LATENCY_BUCKETS = (0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0)  # 2.5s = latency SLO threshold
UNMETERED_PATHS = {"/healthz", "/readyz", "/metrics"}


@dataclass(frozen=True)
class Settings:
    upstream_url: str = "http://vllm.inference.svc:8000"
    api_keys: frozenset[str] = field(default_factory=frozenset)
    auth_disabled: bool = False
    max_tokens_cap: int = 1024
    rate_limit_rpm: int = 60
    upstream_timeout_s: float = 120.0

    @classmethod
    def from_env(cls) -> Settings:
        keys = frozenset(k.strip() for k in os.getenv("API_KEYS", "").split(",") if k.strip())
        return cls(
            upstream_url=os.getenv("UPSTREAM_URL", cls.upstream_url),
            api_keys=keys,
            auth_disabled=os.getenv("AUTH_DISABLED", "false").lower() == "true",
            max_tokens_cap=int(os.getenv("MAX_TOKENS_CAP", cls.max_tokens_cap)),
            rate_limit_rpm=int(os.getenv("RATE_LIMIT_RPM", cls.rate_limit_rpm)),
            upstream_timeout_s=float(os.getenv("UPSTREAM_TIMEOUT_S", cls.upstream_timeout_s)),
        )


class RateLimiter:
    """Fixed-window limiter per API key. In-memory: good enough per pod; use Redis for a global limit."""

    def __init__(self, rpm: int, clock: Callable[[], float] = time.monotonic) -> None:
        self.rpm = rpm
        self.clock = clock
        self._windows: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))

    def allow(self, key: str) -> bool:
        window = int(self.clock() // 60)
        start, count = self._windows[key]
        if start != window:
            start, count = window, 0
        if count >= self.rpm:
            return False
        self._windows[key] = (start, count + 1)
        return True


class Message(BaseModel):
    role: str = Field(pattern="^(system|user|assistant|tool)$")
    content: str


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="allow")  # pass through temperature, top_p, ...

    model: str = Field(min_length=1, max_length=200)
    messages: list[Message] = Field(min_length=1)
    max_tokens: int | None = Field(default=None, ge=1)
    stream: bool = False


def create_app(
    settings: Settings | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> FastAPI:
    settings = settings or Settings.from_env()
    if not settings.auth_disabled and not settings.api_keys:
        raise ValueError("API_KEYS must be set unless AUTH_DISABLED=true")

    registry = CollectorRegistry()
    requests_total = Counter(
        "gateway_requests", "Requests handled by the gateway", ["route", "code"], registry=registry
    )
    duration = Histogram(
        "gateway_request_duration_seconds", "End-to-end request latency", ["route"],
        buckets=LATENCY_BUCKETS, registry=registry,
    )
    limiter = RateLimiter(settings.rate_limit_rpm, clock=clock)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.upstream = httpx.AsyncClient(
            base_url=settings.upstream_url, timeout=settings.upstream_timeout_s, transport=transport
        )
        yield
        await app.state.upstream.aclose()

    app = FastAPI(title="inference-gateway", version="0.1.0", lifespan=lifespan, docs_url=None, redoc_url=None)

    @app.middleware("http")
    async def metrics(request: Request, call_next):
        path = request.url.path
        if path in UNMETERED_PATHS:
            return await call_next(request)
        start = time.perf_counter()
        response = await call_next(request)
        requests_total.labels(route=path, code=str(response.status_code)).inc()
        duration.labels(route=path).observe(time.perf_counter() - start)
        return response

    def caller(request: Request) -> str:
        if settings.auth_disabled:
            return "anonymous"
        header = request.headers.get("authorization", "")
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not any(hmac.compare_digest(token, k) for k in settings.api_keys):
            raise HTTPException(status_code=401, detail="invalid or missing API key")
        return token[-4:]  # identify the caller in limits/logs without keeping the secret

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz(request: Request) -> Response:
        try:
            r = await request.app.state.upstream.get("/health", timeout=2.0)
            ok = r.status_code == 200
        except httpx.HTTPError:
            ok = False
        return JSONResponse({"upstream": "ok" if ok else "unavailable"}, status_code=200 if ok else 503)

    @app.get("/metrics")
    async def prometheus_metrics() -> Response:
        return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)

    @app.post("/v1/chat/completions")
    async def chat(body: ChatRequest, request: Request, who: str = Depends(caller)) -> Response:
        if body.stream:
            raise HTTPException(status_code=400, detail="streaming is not supported by this gateway yet")
        if body.max_tokens is not None and body.max_tokens > settings.max_tokens_cap:
            raise HTTPException(status_code=422, detail=f"max_tokens must be <= {settings.max_tokens_cap}")
        if not limiter.allow(who):
            raise HTTPException(status_code=429, detail="rate limit exceeded", headers={"Retry-After": "60"})

        payload = body.model_dump(exclude_none=True)
        payload.setdefault("max_tokens", settings.max_tokens_cap)
        try:
            upstream = await request.app.state.upstream.post("/v1/chat/completions", json=payload)
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="model server timed out") from None
        except httpx.HTTPError:
            raise HTTPException(status_code=502, detail="model server unreachable") from None

        if upstream.status_code >= 500:
            raise HTTPException(status_code=502, detail="model server error")
        return Response(upstream.content, status_code=upstream.status_code, media_type="application/json")

    return app


def app_factory() -> FastAPI:  # uvicorn --factory app.main:app_factory
    return create_app()
