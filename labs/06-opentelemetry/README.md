# Lab 06 — OpenTelemetry Collector

**Goal:** ship app telemetry over OTLP through one vendor-neutral pipeline.

The collector (`gitops/apps/otel-collector.yaml`, values in `platform/otel/values.yaml`) receives OTLP on `:4317` (gRPC) / `:4318` (HTTP), bound to `0.0.0.0` so `kubectl port-forward` works (the chart default binds to the pod IP only), re-exposes metrics on `:8889` for Prometheus, and prints traces/logs via the `debug` exporter.

## Send telemetry

```bash
kubectl -n observability port-forward svc/otel-collector-opentelemetry-collector 4318:4318
pip install -r labs/06-opentelemetry/requirements.txt
python3 labs/06-opentelemetry/emit.py
```

- Metrics: query `inference_requests_total` in Prometheus/Grafana (via the collector's `prom-exporter` ServiceMonitor).
- Traces: `kubectl -n observability logs deploy/otel-collector-opentelemetry-collector | grep -A5 Span`.

## Exercises

1. Add Grafana Tempo and switch the traces pipeline exporter from `debug` to `otlp` → Tempo.
2. Add the `k8sattributes` processor so every signal carries pod/namespace labels.
3. Instrument the load test (`scripts/loadtest.py`) so each request is a span.
