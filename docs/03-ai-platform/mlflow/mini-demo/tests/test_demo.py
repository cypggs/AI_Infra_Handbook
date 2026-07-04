"""Tests for MLflow mini-demo."""
from mlflow_mini.demo import run_demo


def test_run_demo_end_to_end():
    result = run_demo()
    assert result["model_name"] == "iris-classifier"
    assert result["model_version"] == 1
    assert result["alias"] == "champion"
    assert 0.8 <= result["accuracy"] <= 1.0
    assert isinstance(result["predictions"], list)
    assert len(result["predictions"]) == 3
