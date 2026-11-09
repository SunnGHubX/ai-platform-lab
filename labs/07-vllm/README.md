# Lab 07 — vLLM (LLM inference)

**Goal:** serve an LLM behind an OpenAI-compatible API, observe it, and autoscale it on queue depth.

**Needs:** a node with an NVIDIA GPU and the NVIDIA GPU Operator (or device plugin) so `nvidia.com/gpu` is schedulable.

```bash
make inference                      # applies gitops/root-inference.yaml (vLLM + Triton)
kubectl -n inference get pods -w   # first start downloads weights — give it a few minutes
make vllm-api
```

## Talk to it

```bash
curl -s localhost:8000/v1/models | jq
curl -s localhost:8000/v1/chat/completions -H 'Content-Type: application/json' -d '{
  "model": "qwen",
  "messages": [{"role": "user", "content": "What is KEDA in one sentence?"}],
  "max_tokens": 80
}' | jq -r '.choices[0].message.content'
```

Gated model (e.g. Llama)? `kubectl -n inference create secret generic hf-token --from-literal=token=hf_xxx` and change `--model` in `platform/vllm/deployment.yaml`.

## Scale it

```bash
python3 scripts/loadtest.py --concurrency 64 --requests 500
kubectl -n inference get hpa keda-hpa-vllm -w
```

Watch the **vLLM – AI Platform Lab** dashboard in Grafana: waiting requests climb → KEDA adds replicas (if GPUs are free) → TTFT recovers.

## Exercises

- Put the HF cache on a PVC and compare cold-start time.
- Try `--enable-prefix-caching` and compare TTFT for repeated system prompts.
- Run two models on one GPU with MIG or time-slicing (GPU Operator config).
