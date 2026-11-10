# 20 · Zero-trust networking: default-deny everywhere ★★★

**Track:** Security · zero trust · **Complex (proven on a live cluster)**

**Scenario:** Only `inference-gateway` has a NetworkPolicy. Everything else can talk to everything: a compromised MLflow pod can call vLLM directly and bypass auth, rate limits and SLO metrics.

## Requirements

1. Every namespace with workloads (`inference`, `mlops`, `observability`) gets a **default-deny** (ingress + egress) policy: `platform/*/networkpolicy-default-deny.yaml`.
2. Explicit allows, minimum needed:
   - `vllm` ingress **only** from `inference-gateway` pods and Prometheus (`monitoring` ns) on 8000
   - `mlflow` ingress from `monitoring` and from namespaces labelled `mlflow-client=true`
   - DNS egress (kube-dns **and** NodeLocal DNSCache `169.254.20.10` if you use it) for everyone
   - `otel-collector` ingress on 4317/4318 from any namespace labelled `telemetry=enabled`
3. Policy-as-code: a Rego rule using `conftest test --combine` that fails if a namespace has a Deployment but **no** NetworkPolicy with `podSelector: {}` and both policy types.
4. **Prove it live:** add e2e tests to `tests/e2e/smoke_test.py`:
   - `test_zero_trust_vllm_unreachable_from_mlops`: run a throwaway pod in `mlops` and assert it **cannot** reach `vllm.inference:8000`
   - `test_zero_trust_gateway_path_still_works`: the existing gateway → vLLM path still returns 200

## Acceptance

- [ ] default-deny policies in each workload namespace
- [ ] combined-mode Rego rule + tests
- [ ] the two new e2e tests exist and `make e2e` passes

<details><summary>Hints</summary>

- `kubectl run probe --rm -i --restart=Never --image=busybox:1.36 -n mlops -- wget -T 3 -qO- http://vllm.inference:8000/health` exits non-zero when blocked. Assert on that.
- Kind's default CNI (kindnet) enforces NetworkPolicy in recent versions; the e2e already depends on it.
</details>

**Interview angle:** zero trust inside the cluster (identity + policy per hop), L3/4 NetworkPolicy limits vs L7 (exercise 21), how to roll out default-deny without an outage (audit with flow logs / Cilium Hubble first).

## Validate

```bash
git checkout -b ex/20-<short-name>
make exercise EX=20          # local: ✅/❌ per acceptance check
git push -u origin HEAD       # CI: the `exercise` workflow runs the same checks (strict) + every other pipeline
```
