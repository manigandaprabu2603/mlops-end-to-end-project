"""Find the newest evaluated model for the label entered in CD."""
import argparse
import os
import re

import mlflow
from mlflow import MlflowClient


def main():
    # 1. Read the label passed by the CD workflow.
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    label = parser.parse_args().label
    if not re.fullmatch(r"[0-9]{8}-[1-9][0-9]*", label):
        raise ValueError("Use a label such as 20261102-3")

    # 2. Connect using the MLflow settings provided by the workflow.
    mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
    client = MlflowClient()
    experiment = client.get_experiment_by_name("churn-practice")
    if experiment is None:
        raise ValueError("Run training CI first: churn-practice was not found")

    # 3. Find matching runs with completed evaluation, newest first.
    runs = client.search_runs(
        experiment_ids=[experiment.experiment_id],
        filter_string=(
            f"tags.release_id = '{label}' AND "
            "tags.evaluation_status = 'completed' AND attributes.status = 'FINISHED'"
        ),
        order_by=["attributes.start_time DESC", "attributes.run_id DESC"],
        max_results=1,
    )
    if not runs:
        raise ValueError(f"No evaluated model found for {label}")
    run = runs[0]
    model_uri = run.data.tags["model_uri"]
    if not re.fullmatch(r"(?:runs:/[a-f0-9]{32}/[A-Za-z0-9_-]+|models:/[A-Za-z0-9_-]+)", model_uri):
        raise ValueError("The selected run must contain a logged model URI")

    # 4. Pass these values to later GitHub Actions steps.
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        output.write(f"model_uri={model_uri}\n")
        output.write(f"run_id={run.info.run_id}\n")
    print(f"Selected {label}: {model_uri} (run {run.info.run_id})")


if __name__ == "__main__":
    main()
