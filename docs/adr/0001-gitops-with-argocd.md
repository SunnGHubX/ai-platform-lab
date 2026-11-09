# ADR-0001: GitOps with Argo CD (app-of-apps)

- **Status:** Accepted
- **Date:** 2026-11-09

## Context

The platform runs ~10 components across several namespaces and environments. Changes must be reviewable, reversible and auditable, and cluster drift (manual `kubectl edit`) must not survive.

## Decision

Argo CD with an app-of-apps root per concern (`gitops/root-app.yaml` core, `gitops/root-inference.yaml` opt-in GPU stack), automated sync with `prune` and `selfHeal`, sync waves for CRD ordering.

## Options considered

| Option | Pros | Cons |
|---|---|---|
| Argo CD app-of-apps | UI, drift detection, simple mental model | One Application per component to maintain |
| Argo CD ApplicationSet | One template → many clusters/envs | More indirection; overkill for one cluster |
| Flux | Lightweight, Kustomize-native | No built-in UI; less common in job postings |
| CI `kubectl apply` | Simple | No drift correction, credentials in CI, no pull model |

## Consequences

- Rollback = `git revert`. Audit trail = Git history.
- CRD-dependent apps need sync waves (monitoring at -2, KEDA at -1).
- Move to ApplicationSet when a second cluster appears (study exercise 04).
