# Lab 02 — KEDA (event-driven autoscaling)

**Goal:** scale on signals that matter (queue depth, schedules, Prometheus queries) — including to zero.

KEDA is installed by `gitops/apps/keda.yaml`. This lab uses a throwaway workload so it runs on any laptop.

## 1. Cron scaler (no dependencies)

```bash
kubectl apply -f labs/02-keda/demo.yaml
kubectl -n keda-demo get scaledobject,hpa,deploy -w
```

`demo.yaml` scales `nginx` to 3 replicas during the first 10 minutes of every hour and back to 0 otherwise. Edit the cron window to see it trigger right now.

## 2. Prometheus scaler (the real pattern)

The vLLM ScaledObject in `platform/vllm/scaledobject.yaml` scales on:

```promql
sum(vllm:num_requests_waiting{namespace="inference"})
```

with `threshold: 5` → KEDA targets ~5 waiting requests per replica. Drive it with:

```bash
make vllm-api &
python3 scripts/loadtest.py --concurrency 64 --requests 500
kubectl -n inference get hpa keda-hpa-vllm -w
```

## Exercises

- Set `minReplicaCount: 0` on the demo and confirm the Deployment goes to 0.
- Why is CPU utilization a bad autoscaling signal for GPU inference? (GPU-bound; CPU stays low while queue grows.)
- What does `cooldownPeriod` protect you from on GPU nodes? (Flapping + multi-minute model reloads.)

Cleanup: `kubectl delete -f labs/02-keda/demo.yaml`
