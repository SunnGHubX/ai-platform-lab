# 19 · Kubernetes RBAC least privilege + EKS access entries ★★

**Track:** Security · RBAC · **Common scenario (every platform team does this)**

**Scenario:** Three groups need cluster access:

| Persona | Needs |
|---|---|
| `ml-engineers` | deploy & debug in `mlops` and `inference` only: Deployments, Pods, logs, exec into their pods, port-forward. **No** Secrets read. |
| `oncall` | read-only everywhere incl. events and logs; may `rollout restart` Deployments; **no** Secrets read, no exec |
| `platform-admins` | cluster-admin, but only via a separate break-glass IAM role |

## Requirements

1. `platform/rbac/` (Kustomize, new Argo CD app): `ClusterRole`s + namespaced `RoleBinding`s/`ClusterRoleBinding`s bound to **groups** `ml-engineers`, `oncall`.
2. Terraform `modules/eks-cluster`: new input `access_groups = map(object({ principal_arn, kubernetes_groups }))` → EKS access entries that map IAM roles to those groups (no `AmazonEKSClusterAdminPolicy` except platform-admins).
3. Rego policies (with tests) that **deny**:
   - `verbs: ["*"]` or `resources: ["*"]` in any Role/ClusterRole (except names starting with `system:` or `platform-admin`)
   - any rule granting `get`/`list`/`watch` on `secrets` to a non-admin role
   - bindings to `system:authenticated`, `system:unauthenticated` or `system:anonymous`
   - `ClusterRoleBinding` to `cluster-admin` for anything but `platform-admins`
4. Prove it: a script `platform/rbac/verify.sh` using `kubectl auth can-i --as=x --as-group=<group>` for a matrix of allowed/denied actions (exit non-zero on any mismatch).

## Acceptance

- [ ] `platform/rbac/` builds; passes Conftest including your new rules
- [ ] ≥ 4 new Rego tests
- [ ] `verify.sh` exists with both allow and deny expectations
- [ ] `access_groups` variable in `eks-cluster`

**Interview angle:** why `exec` and `secrets` are the dangerous verbs, aggregated ClusterRoles, impersonation for testing RBAC, IAM → K8s identity mapping on EKS (access entries vs aws-auth).

## Validate

```bash
git checkout -b ex/19-<short-name>
make exercise EX=19          # local: ✅/❌ per acceptance check
git push -u origin HEAD       # CI: the `exercise` workflow runs the same checks (strict) + every other pipeline
```
