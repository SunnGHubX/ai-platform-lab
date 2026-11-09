"""Kubeflow Pipelines (KFP v2) demo: train a model and log it to the in-cluster MLflow."""
from kfp import compiler, dsl

MLFLOW_URI = "http://mlflow.mlops.svc:5000"


@dsl.component(base_image="python:3.12-slim", packages_to_install=["mlflow", "scikit-learn"])
def train(n_estimators: int, mlflow_uri: str) -> float:
    import mlflow
    from sklearn.datasets import load_iris
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split

    mlflow.set_tracking_uri(mlflow_uri)
    mlflow.set_experiment("kfp-iris")
    X_train, X_test, y_train, y_test = train_test_split(*load_iris(return_X_y=True), random_state=42)
    with mlflow.start_run():
        model = RandomForestClassifier(n_estimators=n_estimators).fit(X_train, y_train)
        acc = float(model.score(X_test, y_test))
        mlflow.log_param("n_estimators", n_estimators)
        mlflow.log_metric("accuracy", acc)
        mlflow.sklearn.log_model(model, name="model")
    return acc


@dsl.pipeline(name="iris-train", description="Train on iris, track in MLflow")
def train_pipeline(n_estimators: int = 100):
    train(n_estimators=n_estimators, mlflow_uri=MLFLOW_URI)


if __name__ == "__main__":
    compiler.Compiler().compile(train_pipeline, "train_pipeline.yaml")
    print("wrote train_pipeline.yaml")
