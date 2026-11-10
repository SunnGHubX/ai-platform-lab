# Troubleshooting

Two halves: the **workflows and tools** that help you debug, and a **field guide** per failure class (the triage tool links straight to these sections).

## Workflows & tools

| Need | Workflow (Actions tab) | Locally |
|---|---|---|
| "What's wrong with this cluster?" | — | `make triage [PROM=http://localhost:9090]` → bundle dir with `report.md`, raw JSON, logs (incl. `--previous`), `describe` output |
| "Why did CI fail?" | **ci-doctor** runs automatically on every failed pipeline: classifies the failure (🔁 transient vs 🔴 real, which tool, which test) and keeps one comment on the PR. Run it by hand for any past run with its `run_id` | `make doctor RUN=<run id>` |
| Reproduce one failing test in CI with debug output | **run-tests**: pick a suite, a filter (`pytest -k`, module path, OPA `--run`), tick *debug* (`-vv -s`, `TF_LOG=DEBUG`, OPA `--explain`). Uploads JUnit + debug logs | `SUITE=gateway FILTER=rate_limit DEBUG=true .github/scripts/run_suite.sh` |
| Practise incidents / prove triage works | **troubleshoot**: break-fix drills on kind, one runner per scenario. Tick *practice* to hide the answer, then investigate the uploaded bundle | `make drill SCENARIO=netpol-dns PRACTICE=1` (`KEEP_CLUSTER=true` to keep poking) |
| e2e failed, now what? | **e2e** uploads `e2e-triage-bundle` on failure; ci-doctor names the failing tests | `KEEP_CLUSTER=true make e2e`, then `make triage` |
| Is the repo healthy? | **repo-health** (weekly): broken doc links, chart/image version drift, exercise board | `make health` |

### Break-fix drill catalogue ([`tests/drills/scenarios.yaml`](../tests/drills/scenarios.yaml))

| Scenario | Symptom you'd see | Triage must report |
|---|---|---|
| `oom` | gateway restarts every few seconds | `OOMKILLED` |
| `image-pull` | rollout hangs halfway | `IMAGE_PULL` |
| `gpu-pending` | model server stuck Pending | `UNSCHEDULABLE_GPU` |
| `selector-mismatch` | 502s while vLLM looks healthy | `SERVICE_NO_ENDPOINTS` |
| `netpol-dns` | gateway unready after "tightening egress" | `NETPOL_NO_DNS` |
| `keda-broken` | queue high, replicas stuck at 1 | `SCALEDOBJECT_NOT_READY` |
| `probe-failure` | pods Running but 0/1 Ready | `PROBE_FAILING` |
| `slo-burn` | spike of 5xx | `ALERT_FIRING` (InferenceAvailabilityFastBurn) |

Each drill: inject fault → show the symptom → triage must detect it → apply fix → verify the gateway serves 200 again. Add your own by appending to `scenarios.yaml` (the static tests in `tests/drills/test_scenarios.py` catch typos before a 15-minute run).

### A debugging loop that works

1. **Scope:** what changed (deploy, config, traffic, upstream)? `argocd app history`, `git log`, `kubectl rollout history`.
2. **Symptom → layer:** user errors (gateway metrics) → Service/endpoints → pods → node/scheduling → network policy/DNS → cloud.
3. **Collect once, read many:** `make triage` before you start changing things; the bundle is your evidence.
4. **Mitigate first** (rollback via Git revert), root-cause second.
5. **Close the loop:** a drill, a test, or an alert so it can't recur silently.

---

## Field guide

### OOMKilled

**Signals:** `lastState.terminated.reason: OOMKilled`, exit code 137, restarts climbing.

```bash
kubectl -n <ns> get pod <pod> -o jsonpath='{.status.containerStatuses[*].lastState}'
kubectl top pod -n <ns> --containers
```
```promql
max by (pod, container) (container_memory_working_set_bytes{namespace="<ns>"}) / on (pod, container) group_left
max by (pod, container) (kube_pod_container_resource_limits{resource="memory", namespace="<ns>"})
```
**Usual causes:** limit set below startup footprint; more worker processes than expected (MLflow 3.x job consumers, gunicorn/uvicorn `--workers`); memory leak (steady climb). **Fix:** size from observed working set + headroom; reduce workers; for leaks, a heap profile before raising limits.

### CrashLoopBackOff

**Signals:** waiting reason `CrashLoopBackOff`, `lastState.terminated.exitCode` ≠ 137.

```bash
kubectl -n <ns> logs <pod> --previous      # the crash is in the PREVIOUS container's logs
kubectl -n <ns> describe pod <pod> | sed -n '/Last State/,/Ready/p'
```
Exit 1 = app error (config, missing env/secret, failed migration); 126/127 = bad entrypoint; 139 = segfault.

### Image pull errors

**Signals:** `ImagePullBackOff`, `ErrImagePull`, `ErrImageNeverPull`.

```bash
kubectl -n <ns> describe pod <pod> | grep -A3 -i "failed to pull"
```
`not found` → wrong tag/repo (immutable tags help); `unauthorized`/`403` → registry auth, ECR policy, or Pod Identity on the node role; `i/o timeout` → no route to the registry (NAT down, missing ECR/S3 VPC endpoints in private subnets).

### Pending pods

**Signals:** phase `Pending`, `PodScheduled=False`. **Read the message** — it names the blocker:

| Message contains | Meaning | Fix |
|---|---|---|
| `Insufficient nvidia.com/gpu` | no free GPU | raise GPU node group `max_size`, check device plugin / GPU Operator, ASG node-template tags for scale-from-zero |
| `untolerated taint {nvidia.com/gpu…}` | pod lacks the toleration | add toleration (Conftest policy enforces this) |
| `Insufficient cpu/memory` | requests too big / cluster full | right-size requests; autoscaler logs |
| `didn't match Pod's node affinity` | selector/affinity typo | compare node labels |
| `unbound immediate PersistentVolumeClaims` | storage class / AZ mismatch | check PVC + StorageClass |

### Failing probes

**Signals:** Running but not Ready; `Unhealthy` events.

```bash
kubectl -n <ns> get events --field-selector involvedObject.name=<pod>,reason=Unhealthy
```
`statuscode: 404` → wrong path · `connection refused` → wrong port / app not listening / still starting (add a `startupProbe`) · `context deadline exceeded` → slow app or CPU throttling (check `container_cpu_cfs_throttled_periods_total`). Liveness failures restart the container; readiness failures only remove it from Service endpoints.

### Service has no endpoints

**Signals:** clients get 502/503/connection refused; pods look healthy.

```bash
kubectl -n <ns> get endpointslices -l kubernetes.io/service-name=<svc>
kubectl -n <ns> get svc <svc> -o jsonpath='{.spec.selector}'; kubectl -n <ns> get pods --show-labels
```
Zero endpoints + no matching pods → selector/label mismatch. Endpoints exist but `ready: false` → probes (above). Port mismatch → `targetPort` name/number vs container port.

### NetworkPolicy blocks DNS

**Signals:** after adding/tightening egress, apps log name-resolution failures or readiness fails on upstream checks.

```bash
kubectl -n <ns> get networkpolicy -o yaml | grep -A12 egress
kubectl -n <ns> exec <pod> -- python3 -c "import socket; print(socket.gethostbyname('kubernetes.default'))"
```
Every egress-restricted pod needs UDP **and** TCP 53 to kube-dns (`k8s-app: kube-dns` in `kube-system`), plus NodeLocal DNSCache's link-local IP (`169.254.20.10`) if your cluster uses it.
