# Lab 03 — Kubeflow

**Goal:** run an ML pipeline on Kubernetes and log its results to MLflow.

Full Kubeflow is heavy (Istio, Dex, many controllers) and is **not** part of the default app-of-apps. For a lab, install only **Kubeflow Pipelines (KFP)** standalone.

## Install KFP standalone

Follow the current instructions in the Kubeflow docs for standalone Pipelines (pin the version you install):
https://www.kubeflow.org/docs/components/pipelines/operator-guides/installation/

```bash
export PIPELINE_VERSION=<pick from https://github.com/kubeflow/pipelines/releases>
kubectl apply -k "github.com/kubeflow/pipelines/manifests/kustomize/cluster-scoped-resources?ref=$PIPELINE_VERSION"
kubectl wait --for condition=established --timeout=60s crd/applications.app.k8s.io
kubectl apply -k "github.com/kubeflow/pipelines/manifests/kustomize/env/platform-agnostic?ref=$PIPELINE_VERSION"
kubectl -n kubeflow port-forward svc/ml-pipeline-ui 8081:80
```

Want the full platform instead? Use https://github.com/kubeflow/manifests (needs ~16 GB RAM / 8 CPU).

## Run the pipeline

```bash
pip install kfp
python3 labs/03-kubeflow/pipeline.py        # compiles train_pipeline.yaml
```

Upload `train_pipeline.yaml` in the KFP UI and run it. The training step logs to MLflow at `http://mlflow.mlops.svc:5000` — check the `kfp-iris` experiment in the MLflow UI afterwards.

## Exercise — GitOps it

Turn this into an Argo CD Application under `gitops/apps/` pointing at the KFP kustomize path with a pinned `ref`.
