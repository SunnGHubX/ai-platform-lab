# Runbook: VLLMQueueBacklog / VLLMKVCacheSaturated

Cause-based tickets: they explain *why* the SLO alerts may fire soon.

## Is KEDA scaling?

```bash
kubectl -n inference get scaledobject vllm -o wide        # READY/ACTIVE should be True
kubectl -n inference get hpa keda-hpa-vllm                # TARGETS vs threshold, REPLICAS
kubectl -n keda logs deploy/keda-operator --tail=100 | grep -i vllm
```

- `READY=False` → KEDA can't query Prometheus. Check `serverAddress` in `platform/vllm/scaledobject.yaml` and that `kps-prometheus` is up.
- HPA at `maxReplicaCount` → raise it **and** make sure the GPU node group `max_size` can back it.
- New replicas `Pending` → no GPU capacity: `kubectl get events -n inference --field-selector reason=FailedScheduling`.

## Is the GPU node group scaling?

```bash
kubectl -n kube-system logs deploy/cluster-autoscaler --tail=200 | grep -iE "gpu|scale up"
aws autoscaling describe-auto-scaling-groups --query "AutoScalingGroups[?contains(AutoScalingGroupName,'gpu')].[DesiredCapacity,MaxSize]"
```

Scale-from-zero needs the ASG node-template tags (see `terraform/modules/eks-cluster`). Missing tags = autoscaler never picks the GPU group.

## KV cache saturated

Each running sequence holds KV cache proportional to its length. Options, cheapest first: cap `max_tokens` at the gateway → lower `--max-model-len` → more replicas → bigger GPU (`g6e`) → quantised model.
