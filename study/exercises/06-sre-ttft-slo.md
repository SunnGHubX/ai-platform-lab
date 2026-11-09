# 06 · A time-to-first-token SLO with burn-rate alerts ★★★

**Scenario:** chat users care about how fast the first token arrives, not total latency. Define: *95% of requests get their first token in ≤ 1s* (from `vllm:time_to_first_token_seconds`).

## Tasks

1. Check vLLM's histogram buckets for TTFT (`curl vllm:8000/metrics`). Is there a `le="1"` bucket? If not, what do you do? (Pick the nearest bucket and document it, or add a gateway-side histogram.)
2. Add recording rules + FastBurn/SlowBurn alerts to `sre/slo/rules/` (new file `ttft-slo.rules.yaml`).
3. Add promtool tests: firing, not firing, and the **no traffic** case (NaN must not page).
4. Run `python3 sre/slo/build.py`; commit the generated `platform/slo/` files.
5. Write the runbook.

## Acceptance

- [ ] `promtool test rules` green in CI; build drift check passes
- [ ] Runbook linked from `runbook_url`

**Interview angle:** choosing SLIs users feel, burn-rate math (why 14.4?), alert fatigue.

## Validate

```bash
git checkout -b ex/06-<short-name>
make exercise EX=06          # local: ✅/❌ per acceptance check
git push -u origin HEAD       # CI: the `exercise` workflow runs the same checks (strict) + every other pipeline
```
