# Lab 10 — Chaos engineering & game days

**Goal:** prove the SLO alerts, autoscaling and runbooks work *before* a real incident does it for you.

Uses [Chaos Mesh](https://github.com/chaos-mesh/chaos-mesh). Install it in the lab cluster only (it is deliberately not in the app-of-apps):

```bash
helm repo add chaos-mesh https://charts.chaos-mesh.org
helm install chaos-mesh chaos-mesh/chaos-mesh -n chaos-mesh --create-namespace \
  --set chaosDaemon.runtime=containerd --set chaosDaemon.socketPath=/run/containerd/containerd.sock
```

## The method (every experiment)

1. **Steady state:** write down the SLIs before you start (error ratio, p95 latency, replicas).
2. **Hypothesis:** "If X happens, Y stays within SLO / alert Z fires within N minutes."
3. **Blast radius:** one namespace, a time limit (`duration`), an abort plan (`kubectl delete -f`).
4. **Run** with load on: `python3 scripts/loadtest.py --concurrency 32 --requests 2000`.
5. **Observe** in Grafana and Alertmanager.
6. **Learn:** if the hypothesis failed, it's a finding. Write it up with `templates/postmortem.md`.

## Experiments

| File | Fault | Hypothesis to test |
|---|---|---|
| `01-kill-vllm-pod.yaml` | Kill one vLLM pod | Gateway returns 502 for < 1 min; FastBurn does **not** fire (budget absorbs it); Deployment restores the pod |
| `02-gateway-network-delay.yaml` | +800ms latency gateway → vLLM | Latency SLI degrades; **InferenceLatencyFastBurn** fires within ~5 min at sustained load |
| `03-gpu-node-cpu-stress.yaml` | CPU stress on vLLM pods | Tokenization slows; TTFT rises; KEDA does *not* scale (queue not growing): is that the behaviour we want? |
| `04-dns-failure.yaml` | DNS errors for the gateway | Readiness fails → pods removed from Service → 503s → FastBurn pages. Does the runbook lead you to DNS fast? |

## Game day script (60 min, 2+ people)

| Min | Step |
|---|---|
| 0–10 | Brief: steady state, hypotheses, abort criteria, roles (IC, operator, scribe) |
| 10–40 | Run experiments 01 → 02 → 04 under load; scribe logs timestamps of fault, alert, mitigation |
| 40–50 | Compare detection/mitigation times to targets (alert < 5 min, mitigate < 15 min) |
| 50–60 | File action items: missing alerts, unclear runbook steps, autoscaling gaps |
