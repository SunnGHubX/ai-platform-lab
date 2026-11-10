# 13 · Troubleshooting drills

**Hands-on version:** the same failure classes run as live break-fix drills: `make drill SCENARIO=netpol-dns PRACTICE=1` or the **troubleshoot** workflow with *practice* ticked. Diagnose from the bundle before reading the answer. See [docs/troubleshooting.md](../../docs/troubleshooting.md).

Practise out loud: **hypothesis → command → what you expect → what it means**. Timebox each to 10 minutes. Answers in the collapsed sections. Try first!

### A. vLLM pod `Pending` forever after a deploy ★★
`kubectl describe pod` shows `0/5 nodes are available: 2 node(s) had untolerated taint {nvidia.com/gpu: true}, 3 Insufficient nvidia.com/gpu`.
<details><summary>Answer</summary>Two different problems in one line: the pod lacks the `nvidia.com/gpu` toleration (Conftest rule in `policy/` would have caught it), *and* the GPU nodes that do exist are full. Fix the toleration, then check the GPU node group max / ASG scale-from-zero tags / Spot capacity.</details>

### B. Pods in private subnets get `ImagePullBackOff` from ECR, but only in dev ★★
<details><summary>Answer</summary>Dev has `enable_interface_endpoints = false` and a single NAT. If the NAT gateway's AZ had an issue or the route table lost its default route, ECR is unreachable. In staging/prod the `ecr.api`/`ecr.dkr` endpoints + S3 gateway endpoint keep pulls private. Check `aws ec2 describe-route-tables`, NAT state, and pod events for the exact error (`i/o timeout` vs `403`).</details>

### C. KEDA never scales vLLM even though users report slowness ★★★
<details><summary>Answer</summary>Check `kubectl get scaledobject` READY. Common causes: wrong `serverAddress` (`kps-prometheus` vs release-specific service name), query returns empty (metric renamed between vLLM versions, e.g. `gpu_cache_usage_perc` → `kv_cache_usage_perc`), or HPA at `maxReplicaCount`. An empty query result means "0 waiting", so KEDA thinks it's idle.</details>

### D. GPU leaf: storage throughput fine, NCCL all-reduce jobs 5× slower than last week ★★★★
<details><summary>Answer</summary>Classic lossless-fabric regression. Check PFC counters (pause frames) and ECN marks on the GPU leaf uplinks, and DSCP marking on the hosts (RoCE traffic must be DSCP 26 to land in TC3). A host NIC firmware/driver update resetting DSCP/trust mode is a common culprit; so is a PFC storm from one bad NIC. Compare against the generated config. Did someone hand-edit a switch (drift)?</details>

### E. `terraform plan` in prod wants to replace the RDS instance ★★★
<details><summary>Answer</summary>Read *which* attribute forces replacement (`# forces replacement`). Usual suspects: `identifier` changed via a naming refactor (use `moved`/keep name), `db_subnet_group_name` changed, `engine_version` major bump, `storage_encrypted` toggled. Prod has `deletion_protection = true`, so apply would fail. Good, that's the point. Never `-target` your way around it; fix the cause.</details>

### F. After enabling the gateway NetworkPolicy, readiness fails everywhere ★★
<details><summary>Answer</summary>Readiness calls vLLM `/health`. Egress to vLLM on 8000 is allowed, but DNS to `kube-dns` must also be allowed (it is, UDP+TCP 53). If the cluster uses NodeLocal DNSCache, DNS goes to a link-local IP on the node, not to kube-dns pods, so the policy blocks it. Allow egress to `169.254.20.10/32` or the node-local CIDR.</details>

### G. Error budget burning, but every dashboard shows vLLM healthy ★★★
<details><summary>Answer</summary>The SLI is measured at the gateway. Look at `gateway_requests_total` by `code`: 502s with healthy vLLM point at the path between them: NetworkPolicy, Service selector mismatch after a label change, DNS, or the gateway timeout being lower than long generations (504). Also check whether only one gateway pod is failing (bad node).</details>

## Validate

```bash
git checkout -b ex/13-<short-name>
make exercise EX=13          # local: ✅/❌ per acceptance check
git push -u origin HEAD       # CI: the `exercise` workflow runs the same checks (strict) + every other pipeline
```
