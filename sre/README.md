# SRE practice

How this platform is operated, not just deployed.

| Artifact | Where |
|---|---|
| SLO + alert rules (source of truth) | [`sre/slo/rules/`](slo/rules) |
| Alert unit tests (`promtool test rules`) | [`sre/slo/tests/`](slo/tests) |
| Generated PrometheusRule (deployed by Argo CD) | [`platform/slo/`](../platform/slo) ← `python3 sre/slo/build.py` |
| Runbooks (linked from every alert) | [`docs/runbooks/`](../docs/runbooks) |
| Postmortem / runbook / ADR / design-doc templates | [`templates/`](../templates) |
| Chaos experiments | [`labs/10-chaos-engineering/`](../labs/10-chaos-engineering) |
| Load generator | [`scripts/loadtest.py`](../scripts/loadtest.py) |

## SLOs

| SLO | SLI | Target (30d) | Error budget |
|---|---|---|---|
| Inference availability | non-5xx responses / all responses at the gateway | 99.5% | 0.5% ≈ 3h 36m of full outage |
| Inference latency | requests ≤ 2.5s / all requests | 95% | 5% |

Why at the **gateway**? It's the closest point to the user that we control. vLLM metrics are *causes* (queue depth, KV cache), so they become ticket-level alerts, not pages.

Why 4xx don't count: a client sending a bad request or hitting its rate limit isn't the platform failing. There's a unit test for this.

## Alerting: multi-window, multi-burn-rate

| Alert | Burn rate | Long / short window | Budget used when it fires | Action |
|---|---|---|---|---|
| FastBurn | 14.4× | 1h / 5m | 2% | page |
| SlowBurn | 6× | 6h / 30m | 5% | page |
| BudgetDrain | 1× | 3d / 1d | 10% | ticket |

The short window makes alerts **reset quickly** after mitigation; the long window keeps them from **flapping** on a blip.

## Error budget policy

| Budget remaining (30d) | Policy |
|---|---|
| > 50% | Ship freely. Run chaos experiments. |
| 25–50% | Risky changes (engine upgrades, new models) need a rollback plan in the PR. |
| < 25% | Feature freeze for the service; reliability work first. |
| Exhausted | Only fixes and reliability work merge until the budget recovers. Postmortem required. |

## Incident process (lightweight)

1. **Detect**: SLO alert pages on-call.
2. **Triage** (≤ 5 min): confirm impact with the runbook. Declare SEV1/2/3 in `#incidents`.
3. **Roles**: Incident Commander (coordinates), Ops (hands on keyboard), Comms (updates every 30 min). One person can hold two roles in a small team.
4. **Mitigate first**: rollback (`git revert` → Argo CD), scale out, shed load. Root cause later.
5. **Resolve**: confirm SLIs are back within SLO for 30 min.
6. **Learn**: blameless postmortem within 5 business days for SEV1/2 or > 5% budget burned. Action items get owners and tickets.

## Toil budget

Target < 50% of on-call time on toil. Anything done by hand twice gets a ticket to automate (Terraform, a Makefile target, a KEDA rule, a runbook command).

## Unit-testing the alerts

```bash
docker run --rm -v "$PWD:/w" -w /w --entrypoint promtool prom/prometheus check rules sre/slo/rules/inference-slo.rules.yaml
docker run --rm -v "$PWD:/w" -w /w/sre/slo/tests --entrypoint promtool prom/prometheus test rules inference-slo.test.yaml
python3 sre/slo/build.py   # regenerate platform/slo after editing rules
```
