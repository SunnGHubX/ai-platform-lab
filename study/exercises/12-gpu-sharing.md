# 12 · Share GPUs: MIG and time-slicing ★★★

## Tasks

1. Install the NVIDIA GPU Operator via Argo CD with `driver.enabled=false`, `toolkit.enabled=false` (Ansible role `gpu_node` owns them).
2. **Time-slicing:** ConfigMap that advertises each L4/A10G as 4 `nvidia.com/gpu` replicas. Run two small vLLM models on one GPU (`--gpu-memory-utilization 0.45` each). Measure TTFT and throughput vs one model alone.
3. **MIG** (A100/H100 only, or read and design): `mig.strategy: mixed`, profiles `1g.10gb` and `3g.40gb`; request `nvidia.com/mig-1g.10gb`.
4. Add a Rego rule: pods requesting MIG resources must not also request `nvidia.com/gpu`.

## Acceptance

- [ ] Benchmark table in the PR (alone vs time-sliced)
- [ ] Policy test for the MIG rule

**Interview angle:** isolation (MIG = hardware, time-slicing = none), noisy neighbours, when each is appropriate for inference vs training.
