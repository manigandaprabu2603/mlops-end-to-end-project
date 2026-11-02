"""Load the trained model from MLflow and record its test scores."""
import json
from pathlib import Path

import mlflow
import mlflow.sklearn
import pandas as pd
import yaml
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score


def main():
    # 1. Find the training run and connect to its MLflow server.
    run = json.loads(Path("reports/run.json").read_text(encoding="utf-8"))
    mlflow.set_tracking_uri(run["tracking_uri"])
    model = mlflow.sklearn.load_model(run["model_uri"])

    # 2. Read the test rows and the probability threshold from params.yaml.
    settings = yaml.safe_load(Path("params.yaml").read_text(encoding="utf-8"))["evaluate"]
    threshold = settings["threshold"]
    if not 0 < threshold < 1:
        raise ValueError("evaluate.threshold must be between 0 and 1")
    test_data = pd.read_csv("data/processed/test.csv")
    features = ["tenure_months", "monthly_charges", "support_calls", "month_to_month"]
    actual = test_data["churn"]

    # 3. Predict churn probability. At or above the threshold means churn = 1.
    probabilities = model.predict_proba(test_data[features])[:, 1]
    predictions = (probabilities >= threshold).astype(int)
    metrics = {
        "accuracy": accuracy_score(actual, predictions),
        "precision": precision_score(actual, predictions, zero_division=0),
        "recall": recall_score(actual, predictions, zero_division=0),
        "f1": f1_score(actual, predictions, zero_division=0),
        "roc_auc": roc_auc_score(actual, probabilities),
    }

    # 4. Add the scores to the SAME run as training. No new run is created.
    with mlflow.start_run(run_id=run["run_id"]):
        mlflow.log_metrics(metrics)
        mlflow.log_metric("decision_threshold", threshold)
        mlflow.set_tag("evaluation_status", "completed")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
