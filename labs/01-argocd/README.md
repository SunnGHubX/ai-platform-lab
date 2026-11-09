# Lab 01 — Argo CD (GitOps)

**Goal:** understand app-of-apps, sync waves and self-heal by breaking things on purpose.

## Steps

1. Bootstrap (from repo root): `make cluster bootstrap`
2. Open the UI: `make argocd-ui` → https://localhost:8080, user `admin`, password from `make argocd-password`.
3. Watch the **root** app create `monitoring` → `keda`/`otel-collector` → `mlflow` in wave order:
   ```bash
   kubectl -n argocd get applications -w
   ```

## Exercises

| # | Do this | Expect |
|---|---|---|
| 1 | `kubectl -n mlops scale deploy/mlflow --replicas=0` | Argo CD reverts to 1 within seconds (`selfHeal: true`). |
| 2 | `kubectl -n mlops delete svc mlflow` | Recreated automatically. |
| 3 | Change `resources.requests.memory` in `platform/mlflow/deployment.yaml`, commit, push | New ReplicaSet rolls out — no kubectl. |
| 4 | Delete `gitops/apps/mlflow.yaml`, push | `prune: true` removes the whole MLflow app. Revert the commit to bring it back. |
| 5 | Run `argocd app diff mlflow` after a manual `kubectl edit` | See drift Argo CD would undo. |

## Talking points (interviews)

- Why app-of-apps vs ApplicationSet? (ApplicationSet shines for many clusters/envs from one template.)
- Why `ServerSideApply=true` for kube-prometheus-stack? (CRDs exceed the 262 KB last-applied annotation.)
- How would you promote dev → prod? (Separate `targetRevision` per env, or env overlays + PR-based promotion.)
