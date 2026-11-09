# Lab 04 — MLflow (tracking + model registry)

**Goal:** track experiments, register a model, and promote it with an alias.

MLflow is deployed by `gitops/apps/mlflow.yaml` (SQLite + PVC — fine for a lab; use Postgres + S3/MinIO in prod).

```bash
make mlflow-ui                         # http://localhost:5000
python3 -m venv .venv && . .venv/bin/activate
pip install -r labs/04-mlflow/requirements.txt   # client version = server version
python3 labs/04-mlflow/train.py --runs 5
```

Then in the UI:
1. Compare the 5 runs in the `iris-rf` experiment (sort by `accuracy`).
2. Open **Models → iris-rf** — the best run was registered and given the alias `champion`.
3. Load it by alias anywhere: `mlflow.pyfunc.load_model("models:/iris-rf@champion")`.

## Exercises

- Serve the champion locally: `mlflow models serve -m "models:/iris-rf@champion" -p 5001 --env-manager local`.
- Write a CI step that only moves `@champion` if the new run beats the current champion's accuracy.
