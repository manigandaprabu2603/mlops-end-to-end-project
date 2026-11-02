# Deploy a saved MLflow model to EKS

Choose one path, or run both in separate namespaces:

| Path | Workflow | How the model reaches EKS |
| --- | --- | --- |
| [Docker](docker/README.md) | `CD - Docker model to EKS` | CD downloads the model and includes it in an ECR image |
| [KServe](kserve/README.md) | `CD - KServe model to EKS` | CD uploads the model to S3; an installed KServe runtime serves it |

Both workflows are manual and run from `main` on GitHub-hosted runners.

## Selecting a model

1. Run the updated CI workflow. Training records the model URI and release label in MLflow; evaluation marks the run `evaluation_status=completed` after logging its scores.
2. Start either CD workflow and enter a label such as `20261025-3` in **model_label**.
3. CD selects the newest training run with that label whose evaluation completed and whose MLflow status is `FINISHED`.
4. CD resolves the exact model URI once and uses it throughout deployment. The selected label, run ID and URI appear in the Actions log and as Kubernetes annotations.

## Prerequisites

- Complete [MLflow hosting](../eks-cluster-and-mlflow-setup/README.md) and training CI first.
- Reuse the existing AWS and MLflow repository secrets listed in [the main README](../README.md#github-actions-ci).
- The IAM user used by Docker CD needs ECR image push/read permissions. KServe CD needs S3 upload permissions for its serving prefix. Both need `eks:DescribeCluster`, an EKS access entry (or existing cluster access) and Kubernetes permissions to manage the resources in the chosen namespace. DVC read permissions alone are insufficient. Node IAM roles need ECR image pull access for Docker serving; the KServe service account needs S3 read access. See [EKS access entries](https://docs.aws.amazon.com/eks/latest/userguide/access-entries.html).
- **GitHub-hosted runners must reach the EKS Kubernetes API.** The cluster template allows only your workstation IP. Configure runner network access before CD; AWS credentials do not bypass that restriction. Standard hosted runners have changing outbound IPs, so your workstation `/32` will not work for them. Choose an appropriate network access arrangement for your cluster before running deployment. MLflow's public NLB exposes only MLflow, not the Kubernetes API.
- KServe additionally needs its controller, CRDs, a compatible installed runtime and S3 service-account access. See its separate guide below.

These files do not change your EKS API access rules, install KServe, or create AWS resources automatically.

## One-time setup

As a cluster administrator, create the namespaces. Run from the repository root with your AWS profile and region configured:

```powershell
aws eks update-kubeconfig --name mlops-practice --region ap-south-1
kubectl create namespace inference-docker
kubectl create namespace inference-kserve
```

For Docker serving, create the ECR repository:

```powershell
aws ecr create-repository --repository-name churn-docker --image-tag-mutability IMMUTABLE --region ap-south-1
```

Keep the existing MLflow variables/secrets and add these GitHub repository variables:

| Variable | Example |
| --- | --- |
| `EKS_CLUSTER_NAME` | `mlops-practice` |
| `KUBECTL_VERSION` | `v1.35.0` for a Kubernetes 1.35 cluster; match your actual cluster |
| `DOCKER_ECR_REPOSITORY` | `churn-docker` |

For KServe, add the S3 settings in [its setup guide](kserve/README.md#4-configure-github-and-deploy).

Set up GitHub environments `docker-serving` and `kserve-serving`; restrict deployment to `main` and optionally require approval. The workflows use IAM user secrets, as training does. GitHub authentication needs no additional OIDC role. KServe uses a separate pod IAM role for S3 reads, configured in its guide.

## Access and cost

Both model endpoints use private `ClusterIP` Services, so they add no AWS LoadBalancer. Use the port-forward commands in each guide. MLflow can stay on its existing endpoint while both serving namespaces exist. Each model uses one replica with small CPU/memory requests. KServe adds controller overhead; check node capacity before running all services together. The existing single-node lab may need you to run one serving path at a time. No node size or autoscaling settings are changed here.

The current MLflow HTTP lab endpoint does not encrypt credentials or traffic. Both deployment paths reuse it; use HTTPS before sensitive or production use. The serving endpoints are unauthenticated and intended for private lab access.

