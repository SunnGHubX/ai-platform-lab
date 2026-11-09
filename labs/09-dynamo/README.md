# Lab 09 — NVIDIA Dynamo (distributed inference) · advanced

**Goal:** understand *why* single-replica serving stops scaling and how Dynamo splits the work.

Dynamo sits above engines like vLLM, SGLang and TensorRT-LLM and adds:
- **Disaggregated serving** — prefill (prompt processing, compute-bound) and decode (token generation, memory-bound) on separate GPU workers.
- **KV-cache-aware routing** — send a request to the worker that already holds its prefix.
- **Planner** — SLA-driven scaling of prefill vs decode workers.

**Needs:** multi-GPU node(s), GPU Operator, NGC access. Not part of the default app-of-apps.

## Install the platform

Check the current release first: https://github.com/ai-dynamo/dynamo/releases and the Kubernetes install guide in the Dynamo docs (https://docs.nvidia.com/dynamo/).

```bash
export RELEASE_VERSION=<latest stable from the releases page>
export NAMESPACE=dynamo-system
helm install dynamo-crds oci://helm.ngc.nvidia.com/nvidia/ai-dynamo/charts/dynamo-crds \
  --version "$RELEASE_VERSION" --namespace default
helm install dynamo-platform oci://helm.ngc.nvidia.com/nvidia/ai-dynamo/charts/dynamo-platform \
  --version "$RELEASE_VERSION" --namespace "$NAMESPACE" --create-namespace
kubectl get crd | grep dynamo
kubectl -n "$NAMESPACE" get pods
```

Then deploy one of the vLLM `DynamoGraphDeployment` examples from the Dynamo repo (aggregated first, then disaggregated) into your namespace.

## Exercises

1. Run the same load test (`scripts/loadtest.py`) against aggregated vs disaggregated graphs; compare TTFT p95 and tokens/s.
2. Convert the two Helm installs into Argo CD Applications in `gitops/apps-inference/`.
3. Write up the results in this folder — that's a strong portfolio artifact.
