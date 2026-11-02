"""Download the selected MLflow model for Docker or KServe."""
import argparse
import re
import shutil
from pathlib import Path

import mlflow


def main():
    # 1. Read the model URI and destination supplied by the CD workflow.
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-uri", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"(?:runs:/[a-f0-9]{32}/[A-Za-z0-9_-]+|models:/[A-Za-z0-9_-]+)", args.model_uri):
        raise ValueError("Use the logged model URI selected by CD")

    # 2. Download the complete folder, including model.pkl and MLmodel.
    source = Path(mlflow.artifacts.download_artifacts(artifact_uri=args.model_uri))
    if not (source / "MLmodel").is_file():
        raise ValueError("The download is not a complete MLflow model folder")
    destination = Path(args.output)
    destination.mkdir(parents=True, exist_ok=True)
    if any(destination.iterdir()):
        raise ValueError("Use an empty destination to avoid mixing model files")

    # 3. Copy the model files into the deployment folder.
    for item in source.iterdir():
        if item.is_dir():
            shutil.copytree(item, destination / item.name)
        else:
            shutil.copy2(item, destination / item.name)

    print(f"Downloaded {args.model_uri} to {destination}")


if __name__ == "__main__":
    main()
