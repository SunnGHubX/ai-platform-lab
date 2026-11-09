# Lab 08 — NVIDIA Triton Inference Server

**Goal:** serve models from a model repository with the KServe v2 protocol and Prometheus metrics.

Triton is deployed by `make inference`. The demo model `add_sub` is a Python-backend model on CPU (see `platform/triton/model_repository/`) so it runs without a GPU — the image is large (~9 GB), so the first pull takes a while.

```bash
kubectl -n inference port-forward svc/triton 8000:8000 8002:8002
curl -s localhost:8000/v2/health/ready -o /dev/null -w '%{http_code}\n'   # 200
curl -s localhost:8000/v2/models/add_sub | jq
python3 labs/08-triton/client.py
curl -s localhost:8002/metrics | grep nv_inference_request_success
```

## Exercises

1. Export a small PyTorch model to ONNX, add it to the model repo with `KIND_GPU`, uncomment the GPU limit.
2. Enable dynamic batching (`dynamic_batching { }` in `config.pbtxt`) and measure with `perf_analyzer` from the `-py3-sdk` image.
3. Move the model repository to S3/MinIO: `--model-repository=s3://...`.
4. Compare Triton's vLLM backend (`xx.yy-vllm-python-py3` image) with standalone vLLM from Lab 07.
