# Architecture

## Design goals

- **Everything from Git.** After bootstrap (plus one `make inference` for the opt-in GPU stack), no `kubectl apply` by hand. Argo CD's root Application watches `gitops/apps/`, and each child Application points at either an upstream Helm chart (with values from `platform/`) or a Kustomize directory in `platform/`.
- **Scale on the signal that matters.** CPU is a poor proxy for LLM load. KEDA scales vLLM on `vllm:num_requests_waiting` (queue depth) scraped by Prometheus.
- **One observability plane.** Prometheus scrapes model servers directly; apps that emit OTLP go through the OpenTelemetry Collector, which re-exposes them as Prometheus metrics.
- **Laptop-friendly by default, GPU-ready by design.** Non-GPU components run on kind. GPU workloads request `nvidia.com/gpu` and tolerate the standard GPU taint.

## Sync order (sync waves)

| Wave | Applications | Why |
|---|---|---|
| -2 | monitoring | Installs the ServiceMonitor CRDs everything else uses |
| -1 | keda, otel-collector | Installs ScaledObject CRD; telemetry pipeline |
| 0 | mlflow | Workloads |

The opt-in `root-inference` app-of-apps then deploys **triton** (wave 0) and **vllm** (wave 1). It's applied after the core stack, so the ServiceMonitor and ScaledObject CRDs already exist.

## Request flow (vLLM)

1. Client → `vllm` Service (`:8000`, OpenAI-compatible `/v1/chat/completions`).
2. vLLM exposes `/metrics` → `ServiceMonitor` → Prometheus.
3. KEDA's Prometheus scaler queries `sum(vllm:num_requests_waiting)`; when > threshold per replica, it scales the Deployment (1 → N, bounded by GPUs available).
4. Grafana shows TTFT, tokens/s, KV-cache usage and queue depth.

## Production notes

- Swap kind for EKS/GKE/on-prem with a GPU node pool; label it and keep the `nvidia.com/gpu` taint.
- Put model weights on a shared PVC or an object-store cache instead of downloading per pod.
- Use an ExternalSecret / Sealed Secret for `HF_TOKEN` and the MLflow DB password — never commit them.
- Replace MLflow's SQLite + local artifacts with Postgres + S3/MinIO.
