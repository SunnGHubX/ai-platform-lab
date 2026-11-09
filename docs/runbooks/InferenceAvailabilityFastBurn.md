# Runbook: InferenceAvailability{FastBurn,SlowBurn,BudgetDrain}

| | |
|---|---|
| **SLO** | 99.5% of gateway requests are non-5xx over 30 days |
| **Severity** | FastBurn / SlowBurn → page · BudgetDrain → ticket |
| **Dashboards** | Grafana → *vLLM – Sunn Platform Lab*, *Kubernetes / Compute Resources / Namespace (inference)* |
| **Owner** | platform team |

## 1. Confirm impact (2 min)

```promql
slo:gateway_errors:ratio_rate5m                      # current error ratio
sum by (code) (rate(gateway_requests_total[5m]))     # which codes?
```

- Mostly **502/504** → upstream (vLLM/Triton) is unhealthy or overloaded → go to §2.
- Mostly **500** → gateway bug → go to §3.
- Errors from **one pod only** → `kubectl -n inference get pods -o wide`; delete the bad pod, then investigate.

## 2. Upstream (vLLM) unhealthy

```bash
kubectl -n inference get pods -l app.kubernetes.io/name=vllm
kubectl -n inference describe pod <vllm-pod> | tail -30      # OOMKilled? Pending on GPU?
kubectl -n inference logs <vllm-pod> --tail=200 | grep -iE "error|cuda|oom"
kubectl get nodes -l workload=gpu
```

| Symptom | Likely cause | Action |
|---|---|---|
| Pods `Pending`, event `Insufficient nvidia.com/gpu` | GPU pool at max / Spot capacity gone | Raise `max_size` or switch the GPU node group to on-demand (Terraform `envs/<env>/eks.tfvars`) |
| `CUDA out of memory` in logs | Context length × concurrency too high | Lower `--max-model-len` or `--gpu-memory-utilization`; roll back the last model change |
| `CrashLoopBackOff` after a deploy | Bad image/model arg | `argocd app rollback vllm` (or revert the Git commit) |
| Healthy pods but 504s | Queue saturation | See [VLLMQueueBacklog](VLLMQueueBacklog.md) |

## 3. Gateway bug

```bash
kubectl -n inference rollout history deploy/inference-gateway
argocd app history inference-gateway
```

If errors started with a deploy: **roll back first, debug second** (revert the commit; Argo CD syncs).

## 4. Communicate

- Page acknowledged → post in `#incidents`: impact, start time, who's IC.
- Update every 30 min until mitigated.
- After mitigation: open a postmortem from [`templates/postmortem.md`](../../templates/postmortem.md) if > 5% of monthly budget burned.

## 5. Escalate

GPU capacity or AWS service issue you can't mitigate in 30 min → escalate to the infra on-call / open an AWS support case.
