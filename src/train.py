"""Train a model and save it in MLflow."""
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import mlflow
import mlflow.sklearn
import pandas as pd
import yaml
from mlflow.models import infer_signature
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def main():
    # 1. Read settings and check the dataset pulled by DVC.
    settings = yaml.safe_load(Path("params.yaml").read_text(encoding="utf-8"))["train"]
    pointer = yaml.safe_load(Path("data/churn.csv.dvc").read_text(encoding="utf-8"))
    dataset_hash = pointer["outs"][0]["md5"]
    actual_hash = hashlib.md5(Path("data/churn.csv").read_bytes()).hexdigest()
    if actual_hash != dataset_hash:
        raise ValueError("Dataset does not match its DVC pointer; run dvc pull first")

    remote_url = os.environ["DVC_S3_REMOTE"]
    remote = urlparse(remote_url)
    if remote.scheme != "s3" or not remote.netloc or remote.username or remote.password:
        raise ValueError("DVC_S3_REMOTE must be an S3 URL without embedded credentials")

    # 2. Split into training rows and test rows. Never train on the test rows.
    data = pd.read_csv("data/churn.csv")
    features = ["tenure_months", "monthly_charges", "support_calls", "month_to_month"]
    train_data, test_data = train_test_split(
        data,
        test_size=settings["test_size"],
        random_state=settings["seed"],
        stratify=data["churn"],
    )
    X_train = train_data[features]  # Input columns used to predict churn.
    y_train = train_data["churn"]  # Known answers: 0 = stays, 1 = churns.

    # 3. Choose the model configured in params.yaml.
    if settings["model"] == "logistic_regression":
        # Scaling and the classifier are saved together as one model.
        model = make_pipeline(
            StandardScaler(),
            LogisticRegression(C=settings["C"], max_iter=1000, random_state=settings["seed"]),
        )
    elif settings["model"] == "random_forest":
        model = RandomForestClassifier(
            n_estimators=settings["n_estimators"],
            max_depth=settings["max_depth"],
            random_state=settings["seed"],
            n_jobs=-1,
        )
    else:
        raise ValueError("train.model must be logistic_regression or random_forest")

    # 4. Train and log the model, settings and dataset version in one MLflow run.
    mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
    mlflow.set_experiment("churn-practice")
    # Use the date and GitHub workflow run number as a readable model label.
    date = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y%m%d")
    release_id = f"{date}-{os.environ['GITHUB_RUN_NUMBER']}"

    with mlflow.start_run(run_name=release_id) as run:
        model.fit(X_train, y_train)
        mlflow.log_params(settings)
        mlflow.set_tags({
            "release_id": release_id,
            "dataset": "synthetic-churn",
            "purpose": "learning",
            "dvc.remote.url": remote_url,
            "dvc.bucket": remote.netloc,
            "dvc.data.hash": dataset_hash,
            "dvc.data.hash_algorithm": "md5",
            "dvc.data.path": "data/churn.csv",
        })
        mlflow.log_artifact("data/churn.csv.dvc", artifact_path="data-version")
        logged_model = mlflow.sklearn.log_model(
            model,
            name=release_id,
            # Describe the input/output columns and the packages needed to load it.
            signature=infer_signature(X_train, model.predict(X_train)),
            input_example=X_train.head(3),
            pip_requirements=["mlflow==3.4.0", "scikit-learn==1.6.1", "pandas==2.2.3"],
        )

        # 5. Pass the test rows and MLflow references to the next CI steps.
        # The model itself is stored in MLflow, without a second local pickle.
        Path("data/processed").mkdir(parents=True, exist_ok=True)
        test_data.to_csv("data/processed/test.csv", index=False)
        Path("reports").mkdir(exist_ok=True)
        run_details = {
            "release_id": release_id,
            "run_id": run.info.run_id,
            "model_uri": logged_model.model_uri,
            "tracking_uri": mlflow.get_tracking_uri(),
        }
        Path("reports/run.json").write_text(json.dumps(run_details, indent=2), encoding="utf-8")
        print(f"Saved model: {release_id}")
        print(f"Model URI: {logged_model.model_uri}")


if __name__ == "__main__":
    main()
