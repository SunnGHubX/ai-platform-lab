# System design: "Design a multi-tenant LLM inference platform"

A 45-minute framework, with this repo as your worked example.

## 1. Clarify (5 min): ask, don't assume

- Tenants: internal teams or external customers? Isolation level (noisy neighbour vs data isolation vs compliance)?
- Models: how many, sizes (7B vs 70B vs MoE), open-weights vs fine-tuned per tenant?
- Traffic: peak RPS, average prompt/output tokens, streaming? Interactive vs batch?
- SLOs: TTFT p95, tokens/s per user, availability.
- Constraints: on-prem GPUs, cloud, both? Budget ($/1M tokens)? Data residency?

## 2. Back-of-envelope (5 min)

- 100 RPS × (500 in + 300 out tokens) ≈ 30k output tok/s.
- One L40S with an 8B model under vLLM at good batching ≈ 2–4k output tok/s → **~10–15 GPUs + headroom (N+2, AZ spread)**.
- KV cache per sequence ≈ 2 × layers × kv_heads × head_dim × bytes × seq_len. This limits concurrency more than FLOPs do.

## 3. High-level design (10 min)

```
clients → API gateway (authN, quotas, rate limit, routing by model/tenant)
        → model router (prefix/KV-aware, e.g. Dynamo / llm-d) → model server pools (vLLM/TRT-LLM) per model
        → GPU node pools (Karpenter/MNG, taints, MIG for small models)
observability: per-tenant SLIs at the gateway, engine metrics (queue, KV cache), DCGM GPU metrics
control plane: GitOps (Argo CD), Terraform for infra, model registry (MLflow) → promotion pipeline
```

## 4. Deep dives (15 min): pick 2–3

| Topic | Points to make |
|---|---|
| Autoscaling | Scale on queue depth / KV usage, not CPU. Cold start = image pull + weight load (minutes): keep warm replicas, pre-pull, local NVMe cache, scale-to-zero only for batch. |
| Multi-tenancy | Quotas at the gateway (tokens/min), priority classes, separate pools for premium tenants, MIG for hard isolation, per-tenant LoRA adapters on shared base models. |
| Reliability | Multi-AZ spread, PDBs, gateway retries with budget, circuit breaking per model, graceful drain (finish in-flight generations). |
| Networking | Front-end: standard VPC/ALB. Back-end for multi-node models: RoCE/InfiniBand, rail-optimised, lossless (PFC/ECN). **This is where your background stands out.** |
| Security | Tenant data never logged by default, prompt/response retention policy, signed images, egress-restricted model servers, secrets in a vault, audit trail. |
| Cost | Spot for batch/async, on-demand for interactive, quantisation (FP8/INT4), right-sizing GPU class per model, utilisation dashboards per tenant. |

## 5. Wrap-up (5 min)

Restate SLOs → what you'd build first (gateway + one model pool + SLO alerts) → what you'd defer (Dynamo disaggregation, multi-region).

## Practice prompts

1. Design a batch embedding pipeline for 1B documents/day (hint: SQS + KEDA + spot GPUs, see `batch-embedder` in the service catalog).
2. Design GPU capacity management across on-prem + cloud burst.
3. Design the network for a 256-GPU training cluster (rails, spine-leaf, oversubscription, RoCE).
4. Design a model promotion pipeline from MLflow registry to production with canaries.
