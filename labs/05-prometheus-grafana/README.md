# Lab 05 — Prometheus + Grafana

**Goal:** observe AI workloads with the metrics that actually matter for inference.

kube-prometheus-stack is deployed by `gitops/apps/monitoring.yaml`. It's configured to pick up **every** ServiceMonitor in the cluster, and Grafana auto-loads any ConfigMap labelled `grafana_dashboard: "1"`.

```bash
make grafana-ui      # http://localhost:3000  admin / prom-operator
kubectl -n monitoring port-forward svc/kps-prometheus 9090:9090
```

The **vLLM – AI Platform Lab** dashboard ships from `platform/vllm/vllm-dashboard.json`.

## PromQL cheat sheet

| Question | Query |
|---|---|
| Queue depth (KEDA signal) | `sum(vllm:num_requests_waiting)` |
| TTFT p95 | `histogram_quantile(0.95, sum(rate(vllm:time_to_first_token_seconds_bucket[5m])) by (le))` |
| Generated tokens/s | `sum(rate(vllm:generation_tokens_total[1m]))` |
| KV-cache pressure | `avg(vllm:kv_cache_usage_perc)` |
| Triton inferences/s | `sum(rate(nv_inference_request_success[1m])) by (model)` |
| Triton avg queue time (µs) | `rate(nv_inference_queue_duration_us[1m]) / rate(nv_inference_request_success[1m])` |
| Scrape targets down | `up == 0` |

## Exercises

1. Add a `PrometheusRule` alerting when TTFT p95 > 2s for 5m. Put it in `platform/vllm/` and let Argo CD deploy it.
2. Add the NVIDIA DCGM exporter (via GPU Operator) and graph `DCGM_FI_DEV_GPU_UTIL` next to queue depth.
