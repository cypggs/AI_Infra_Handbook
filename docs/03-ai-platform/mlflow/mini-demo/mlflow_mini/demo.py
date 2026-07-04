"""End-to-end MLflow mini-demo using SQLite backend and local artifacts."""
from __future__ import annotations

import os
import shutil
import tempfile

import mlflow
import mlflow.sklearn
from mlflow import MlflowClient
from mlflow.models import infer_signature
from sklearn.datasets import load_iris
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split


def run_demo() -> dict:
    tmp = tempfile.mkdtemp(prefix="mlflow-mini-")
    try:
        tracking_uri = f"sqlite:///{os.path.join(tmp, 'mlflow.db')}"
        artifact_root = os.path.join(tmp, "artifacts")

        mlflow.set_tracking_uri(tracking_uri)
        client = MlflowClient()

        experiment_name = "iris-classification"
        client.create_experiment(experiment_name, artifact_location=artifact_root)
        mlflow.set_experiment(experiment_name)

        X, y = load_iris(return_X_y=True)
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        params = {"solver": "lbfgs", "max_iter": 200}
        model = LogisticRegression(**params)
        model.fit(X_train, y_train)
        acc = accuracy_score(y_test, model.predict(X_test))

        with mlflow.start_run(run_name="logistic-regression") as run:
            mlflow.log_params(params)
            mlflow.log_metric("accuracy", acc)
            signature = infer_signature(X_train, model.predict(X_train))
            model_info = mlflow.sklearn.log_model(model, "model", signature=signature)
            run_id = run.info.run_id

        model_name = "iris-classifier"
        client.create_registered_model(model_name)
        mv = client.create_model_version(
            name=model_name,
            source=model_info.model_uri,
            run_id=run_id,
        )
        client.set_registered_model_alias(model_name, "champion", mv.version)

        loaded = mlflow.pyfunc.load_model(f"models:/{model_name}@champion")
        predictions = loaded.predict(X_test[:3])

        return {
            "run_id": run_id,
            "model_name": model_name,
            "model_version": mv.version,
            "alias": "champion",
            "accuracy": acc,
            "predictions": predictions.tolist(),
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    result = run_demo()
    print("Demo result:", result)
