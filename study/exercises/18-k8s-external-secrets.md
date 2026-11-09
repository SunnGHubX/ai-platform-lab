# 18 · No Secret manifests in Git: External Secrets Operator ★★

**Track:** Security · secrets · Kubernetes

**Scenario:** The gateway needs `inference-gateway-api-keys`. Today it's created by hand with `kubectl create secret`, so it's undocumented, never rotated, and lost when the cluster is rebuilt. Committing it (even base64) is not an option.

## Requirements

1. Install **External Secrets Operator** via Argo CD (`gitops/apps/external-secrets.yaml`, chart version pinned).
2. Terraform: the services catalog already creates `ai-platform-<env>/inference-gateway/api-keys` in Secrets Manager (exercise 17 or `secrets = [...]`). Add a **Pod Identity** role for the ESO controller that can `secretsmanager:GetSecretValue` **only** on `arn:...:secret:ai-platform-<env>/*`.
3. `platform/inference-gateway/externalsecret.yaml`: a `SecretStore` (namespaced, not `ClusterSecretStore`, so least privilege) + `ExternalSecret` producing `inference-gateway-api-keys`, `refreshInterval: 1h`.
4. Policy: add a Rego rule to `policy/kubernetes/` that **denies** any `kind: Secret` with `data` or `stringData` in rendered manifests (with tests). The e2e overlay's `secretGenerator` is fine because it lives under `tests/`.

## Acceptance

- [ ] ESO app + `ExternalSecret` + `SecretStore` committed; no `kind: Secret` under `platform/`
- [ ] Rego rule + ≥ 2 tests; `conftest verify` passes
- [ ] ESO IAM scoped to the project prefix

**Interview angle:** ESO vs Secrets Store CSI driver vs Sealed Secrets vs SOPS; secret rotation propagation (pods don't reload env vars, so what do you do?).

## Validate

```bash
git checkout -b ex/18-<short-name>
make exercise EX=18          # local: ✅/❌ per acceptance check
git push -u origin HEAD       # CI: the `exercise` workflow runs the same checks (strict) + every other pipeline
```
