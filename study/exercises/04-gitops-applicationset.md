# 04 · ApplicationSet: one template, three environments ★★★

**Scenario:** dev, staging and prod clusters now exist (from `terraform/`). Copying 10 Applications × 3 envs is how drift starts.

## Tasks

1. Create `gitops/appsets/platform.yaml`: an `ApplicationSet` with a **matrix** generator: `clusters` (label `env`) × `list` of components.
2. Add Kustomize overlays: `platform/vllm/overlays/{dev,staging,prod}`: dev 0–1 replicas on Spot, prod `minReplicaCount: 1`, `maxReplicaCount: 8`.
3. Promotion: dev tracks `main`, staging and prod track **tags** (`targetRevision: release-*`). Document the promotion flow (PR → tag → sync).
4. Add a `syncWindows` entry on an AppProject so prod only auto-syncs Mon–Thu 09:00–16:00.

## Acceptance

- [ ] `kubectl kustomize` builds every overlay; CI kubeconform passes
- [ ] README section "Promotion" with a diagram

**Interview angle:** multi-cluster GitOps, environment promotion, blast-radius control.

## Validate

```bash
git checkout -b ex/04-<short-name>
make exercise EX=04          # local: ✅/❌ per acceptance check
git push -u origin HEAD       # CI: the `exercise` workflow runs the same checks (strict) + every other pipeline
```
