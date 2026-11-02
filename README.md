# ChurnLab: DVC + MLflow practice

A hands-on customer churn project for practicing reproducible training, DVC dataset versioning, MLflow experiment tracking, and GitHub Actions. The training pipeline runs in GitHub Actions using a dataset pulled from your S3 DVC remote. A synthetic starter CSV is included for seeding your bucket.

## Getting started

1. Fork and clone the repository.
2. Follow [the S3 setup guide](data/README.md) to install dependencies, authenticate with AWS, and upload the starter dataset using DVC.
3. Follow the [EKS cluster and MLflow setup guide](eks-cluster-and-mlflow-setup/README.md) to create the cluster, install MLflow with Helm, and configure public NLB access for GitHub-hosted CI.
4. Configure the repository variables and IAM user secrets described under [GitHub Actions](#github-actions-ci).
5. Push to `main` or manually run the workflow from `main` to pull the dataset, train, and evaluate.

## Dataset layout

| Path | Purpose | Storage |
| --- | --- | --- |
| `examples/churn.csv` | Public starter: 3,000 synthetic customer rows | GitHub |
| `data/churn.csv.dvc` | Pointer to the versioned working dataset | GitHub |

## GitHub Actions (CI)

The CI workflow covers these stages:

1. **Setup:** Check out the code, configure Python and AWS credentials, and install dependencies.
2. **Data retrieval:** Pull the pinned dataset from S3 using DVC.
3. **Training:** Train the model and log it in MLflow.
4. **Evaluation:** Evaluate on held-out test data and log metrics in MLflow.

First complete [S3 dataset setup](data/README.md) and [EKS/MLflow setup](eks-cluster-and-mlflow-setup/README.md).

Training CI uses your IAM user's access key ID and secret access key stored in GitHub Actions secrets.

Your existing IAM user needs `s3:ListBucket` restricted to the DVC prefix, `s3:GetBucketLocation` on the bucket, and `s3:GetObject` on the DVC objects.

In your GitHub repository's **Settings > Secrets and variables > Actions > Variables**, set:

| Variable | Value |
| --- | --- |
| `AWS_REGION` | `ap-south-1` |
| `DVC_S3_REMOTE` | `s3://YOUR_DVC_BUCKET/dvc-cache` |
| `MLFLOW_TRACKING_URI` | `http://YOUR_NLB_DNS:5000` from [the MLflow setup guide](eks-cluster-and-mlflow-setup/README.md#7-create-the-public-loadbalancer) |

Replace the placeholders with your values.

In GitHub **Settings > Secrets and variables > Actions > Secrets**, add repository secrets:

- `AWS_ACCESS_KEY_ID`: your IAM user's access key ID.
- `AWS_SECRET_ACCESS_KEY`: the corresponding secret access key.
- `MLFLOW_TRACKING_USERNAME`: your MLflow user.
- `MLFLOW_TRACKING_PASSWORD`: that user's password.

Push your changes to `main`, then open **Actions > Train and evaluate > Run workflow**. CI pulls the dataset with DVC, trains the model, and records its evaluation scores in MLflow. Open experiment `churn-practice` in the MLflow UI to see the results.

## Model deployment (CD)

After running CI with the current dependencies, deploy by entering a model label such as `20261025-3` in either manual CD workflow:

- [Docker to EKS](deployments/docker/README.md): package the selected model into an image and push it to ECR.
- [KServe on EKS](deployments/kserve/README.md): upload the selected model from MLflow to S3, then serve it using an installed KServe runtime.

Both select the newest successfully evaluated run for that label and use its exact model URI. Follow [the CD setup](deployments/README.md) for variables, permissions and EKS API connectivity.
