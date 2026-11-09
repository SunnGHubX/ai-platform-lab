# Runbook: InferenceLatency{FastBurn,SlowBurn}

| | |
|---|---|
| **SLO** | 95% of gateway requests complete in ≤ 2.5s over 30 days |
| **Severity** | page |

## Triage

```promql
histogram_quantile(0.95, sum by (le) (rate(gateway_request_duration_seconds_bucket[5m])))
histogram_quantile(0.95, sum by (le) (rate(vllm:time_to_first_token_seconds_bucket[5m])))
sum(vllm:num_requests_waiting)
avg(vllm:kv_cache_usage_perc)
sum(rate(vllm:generation_tokens_total[5m]))
```

| Gateway p95 high and… | Then |
|---|---|
| vLLM TTFT also high, queue growing | Capacity. Check KEDA (`kubectl -n inference get scaledobject,hpa`) and GPU node availability → [VLLMQueueBacklog](VLLMQueueBacklog.md) |
| vLLM TTFT normal | Latency is in the gateway or network: check gateway CPU throttling, pod restarts, NetworkPolicy/DNS issues |
| KV cache > 95% | Preemption thrash. Reduce `--max-model-len`, cap `max_tokens` at the gateway, add replicas |
| Only long prompts slow | Expected; consider separate SLO per request class or prefix caching |

## Mitigate

1. Scale out: `kubectl -n inference patch scaledobject vllm --type merge -p '{"spec":{"minReplicaCount":2}}'` (then make it permanent in Git).
2. Shed load: lower the gateway rate limit (`RATE_LIMIT_RPM`) for non-critical API keys.
3. Roll back a recent model/engine change.
