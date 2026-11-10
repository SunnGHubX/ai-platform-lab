# 25 · Red-team scenario: "the gateway pod is compromised" ★★★★

**Track:** Security · zero trust · least privilege · **Capstone**

**Scenario:** Assume an attacker has RCE in an `inference-gateway` pod (e.g. a deserialization bug). Your controls should make that a **contained** incident. Prove it with automated attack simulations, not slides.

## Requirements

1. **Threat model** `docs/threat-models/inference-gateway.md`: data-flow diagram (Mermaid), STRIDE table per hop (client → gateway → vLLM, gateway → AWS), existing controls, gaps.
2. **Attack simulations** as e2e tests in `tests/e2e/attack_test.py` (run by `run.sh`). Each one is executed *from inside* the gateway pod (`kubectl exec`) or a pod using its ServiceAccount, and **must fail**:

| Test | Attempt | Control that should stop it |
|---|---|---|
| `test_attack_read_k8s_secrets` | call the API server with the pod's token | `automountServiceAccountToken: false` (no token) + RBAC |
| `test_attack_reach_mlflow` | `wget mlflow.mlops:5000` | NetworkPolicy egress (gateway may only reach vLLM/Triton + DNS) |
| `test_attack_write_filesystem` | `touch /app/backdoor` | `readOnlyRootFilesystem` |
| `test_attack_escalate_privileges` | check `/proc/self/status` CapEff = 0, NoNewPrivs = 1 | dropped caps, `allowPrivilegeEscalation: false` |
| `test_attack_reach_metadata` | `169.254.169.254` | NetworkPolicy egress (and IMDS hop limit on EKS) |

3. For each **gap** your threat model finds, either fix it or document an accepted risk with an owner.

## Acceptance

- [ ] Threat model with a STRIDE table and a Mermaid diagram
- [ ] `tests/e2e/attack_test.py` with ≥ 5 attack tests, wired into `run.sh`
- [ ] `make e2e` passes (all attacks blocked)

<details><summary>Hints</summary>

- The gateway image is minimal Python: no `wget`/`curl`. Use `python3 -c "import urllib.request; ..."` inside `kubectl exec`, and assert the command **fails**.
- `kubectl exec` needs the container to have a shell, so use `python3 -c` directly as the command (exec form).
</details>

**Interview angle:** "assume breach" design, blast-radius thinking, defence in depth with evidence. This is a great story for senior/staff interviews.

## Validate

```bash
git checkout -b ex/25-<short-name>
make exercise EX=25          # local: ✅/❌ per acceptance check
git push -u origin HEAD       # CI: the `exercise` workflow runs the same checks (strict) + every other pipeline
```
