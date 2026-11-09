#!/usr/bin/env python3
"""Run a small hyperparameter sweep, log to MLflow, register the best model as iris-rf@champion."""
import argparse

import mlflow
from mlflow import MlflowClient
from sklearn.datasets import load_iris
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

p = argparse.ArgumentParser()
p.add_argument("--tracking-uri", default="http://localhost:5000")
p.add_argument("--runs", type=int, default=5)
a = p.parse_args()

mlflow.set_tracking_uri(a.tracking_uri)
mlflow.set_experiment("iris-rf")
X_train, X_test, y_train, y_test = train_test_split(*load_iris(return_X_y=True), random_state=7)

best = (None, -1.0)
for i in range(a.runs):
    n, depth = 10 * (i + 1), (i % 3) + 2
    with mlflow.start_run(run_name=f"rf-{n}-{depth}") as run:
        model = RandomForestClassifier(n_estimators=n, max_depth=depth, random_state=0).fit(X_train, y_train)
        acc = model.score(X_test, y_test)
        mlflow.log_params({"n_estimators": n, "max_depth": depth})
        mlflow.log_metric("accuracy", acc)
        mlflow.sklearn.log_model(model, name="model", input_example=X_test[:2])
        print(f"{run.info.run_id}  n={n} depth={depth} acc={acc:.3f}")
        if acc > best[1]:
            best = (run.info.run_id, acc)

mv = mlflow.register_model(f"runs:/{best[0]}/model", "iris-rf")
MlflowClient().set_registered_model_alias("iris-rf", "champion", mv.version)
print(f"registered iris-rf v{mv.version} as @champion (acc={best[1]:.3f})")
