# inference-gateway

A small, deliberately security-focused FastAPI service in front of vLLM/Triton. It exists to exercise a real **DevSecOps pipeline**, not to be a product.

| Concern | How |
|---|---|
| AuthN | Bearer API keys (constant-time compare), refuses to start without keys unless `AUTH_DISABLED=true` |
| Abuse / cost control | Per-key rate limit (`RATE_LIMIT_RPM`), `max_tokens` cap (`MAX_TOKENS_CAP`), streaming off |
| Input validation | Pydantic schema: roles allow-listed, non-empty messages |
| Failure semantics | upstream 5xx → 502, timeout → 504, unreachable → 502 (these drive the SLO) |
| SLIs | `gateway_requests_total{route,code}`, `gateway_request_duration_seconds` (2.5s bucket = SLO threshold) |
| Container | multi-stage, non-root UID 10001, no build tools, read-only root FS in Kubernetes |

## Develop

```bash
cd services/inference-gateway
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
ruff check . && pytest            # 90% coverage gate
API_KEYS=dev-key UPSTREAM_URL=http://localhost:8000 uvicorn --factory app.main:app_factory --port 8080
```

## Pipeline (`.github/workflows/inference-gateway.yaml`)

`ruff` → `pytest` (coverage gate) → `docker build` → **Trivy** image scan (fail on fixable CRITICAL) → **SBOM** (CycloneDX) → on `main`: push to GHCR → **cosign keyless sign** + SBOM attestation.

Verify a published image:

```bash
cosign verify ghcr.io/sunnghubx/inference-gateway:0.1.0 \
  --certificate-identity-regexp 'https://github.com/SunnGHubX/sunn-platform-lab/.*' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```
