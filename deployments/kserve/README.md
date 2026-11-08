# KServe model deployment from S3

Flow: **model label -> select model in MLflow -> download model in CD -> upload folder to S3 -> KServe serves it using an installed runtime**.

Complete the [CD setup](../README.md) first. This path uses standard `predictor.model` configuration with `modelFormat: mlflow` and an S3 `storageUri`. KServe supplies its normal storage initializer and the selected runtime's image.

## 1. Install KServe

The manifest targets **KServe v0.16.0 Standard mode**, without Knative or Istio. With `kubectl` connected to your EKS cluster, run these PowerShell commands once as the cluster administrator:

```powershell
# Install cert-manager for KServe's webhook certificates.
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.21.3/cert-manager.yaml
kubectl wait --for=condition=Available deployment --all -n cert-manager --timeout=300s

# Install KServe CRDs.
helm install kserve-crd oci://ghcr.io/kserve/charts/kserve-crd --version v0.16.0 --namespace kserve --create-namespace --wait --timeout 5m

# Install the controller with the prebuilt MLflow-only runtime.
helm install kserve oci://ghcr.io/kserve/charts/kserve --version v0.16.0 --namespace kserve --set kserve.controller.deploymentMode=Standard --set kserve.controller.gateway.disableIngressCreation=true --set-string kserve.servingruntime.mlserver.tag=1.7.1-mlflow --wait --timeout 5m
```

Use `mlserver:1.7.1-mlflow`, the MLflow-only image. The unsuffixed `1.7.1` image includes other frameworks such as PyTorch and can exhaust the lab node's 20Gi disk while unpacking.

Check the installation:

```powershell
kubectl get pods -n kserve
```

Check the available resources:

```powershell
kubectl get crd inferenceservices.serving.kserve.io
kubectl get clusterservingruntimes
```


## 2. Choose the S3 model prefix

Reuse your existing S3 bucket in `AWS_REGION`, with a separate prefix such as:

```text
s3://YOUR_BUCKET/kserve-models
```

Keep this separate from DVC's `dvc-cache`. The GitHub IAM user needs `s3:PutObject` for the serving prefix, plus applicable KMS permissions if using a customer-managed encryption key. Models are uploaded as complete folders containing `MLmodel`, `model.pkl` and their supporting files.

Each CD execution uploads to a distinct location, for example:

```text
s3://YOUR_BUCKET/kserve-models/20261102-3/123456789-1/
```

Here `20261102-3` is the training model label; `123456789-1` is the CD run ID and attempt. CD creates this path automatically.

## 3. Give the serving pod S3 read access

This setup uses [IAM roles for service accounts](https://kserve.github.io/website/docs/model-serving/storage/providers/s3). This role is for the KServe pod; GitHub CD continues using your existing IAM user secrets.

In IAM, create or reuse a policy named `KServeModelRead` with:

- `s3:GetObject` on `arn:aws:s3:::YOUR_BUCKET/kserve-models/*`.
- `s3:GetBucketLocation` on `arn:aws:s3:::YOUR_BUCKET`.
- `s3:ListBucket` on that bucket, restricted to the `kserve-models` prefix.
- Applicable `kms:Decrypt` permission if the objects use a customer-managed KMS key.

Use the actual prefix if yours differs. The cluster's IAM OIDC provider must be associated (the project cluster configuration already enables it). As the infrastructure administrator, create the role with trust for this specific Kubernetes service account:

```powershell
eksctl create iamserviceaccount --cluster mlops-practice --region ap-south-1 --namespace inference-kserve --name kserve-s3 --role-name KServeModelReadRole --role-only --attach-policy-arn arn:aws:iam::YOUR_ACCOUNT_ID:policy/KServeModelRead --approve
```

`--role-only` creates the IAM role. The CD manifest creates the Kubernetes ServiceAccount and references the role through `KSERVE_S3_ROLE_ARN`.

## 4. Configure GitHub and deploy

Keep the common AWS, EKS and MLflow settings from the shared guide. Add these repository variables:

| Variable | Example |
| --- | --- |
| `KSERVE_MODEL_S3_PREFIX` | `s3://YOUR_BUCKET/kserve-models` |
| `KSERVE_S3_ROLE_ARN` | `arn:aws:iam::YOUR_ACCOUNT_ID:role/KServeModelReadRole` |

The CD identity needs namespace permissions for InferenceServices and ServiceAccounts, plus Services and read/watch access to Deployments. It also needs permission to read the `kserve-mlserver` cluster runtime.

In GitHub, choose **Actions -> CD - KServe model to EKS -> Run workflow**, select `main`, and enter the model label. CD resolves its model URI once, downloads the model, uploads the folder to S3 and replaces the placeholders in `inferenceservice.yaml` before applying it.

The workflow uses `kubectl wait` for the predictor Deployment and its new S3 path, then waits for its pods to become available with `kubectl rollout status`.

| File | Purpose |
| --- | --- |
| `inferenceservice.yaml` | S3 service account, standard model predictor and private access Service |
| `request.json` | Example v2 prediction request |

## 5. Access the model

After CD succeeds:

```powershell
kubectl port-forward -n inference-kserve service/churn-kserve-access 8082:80
```

In another terminal, from the repository root:

```powershell
$response = Invoke-RestMethod -Method Post -Uri http://localhost:8082/v2/models/churn-kserve/infer -ContentType application/json -InFile deployments/kserve/request.json
$response | ConvertTo-Json -Depth 10
$response.outputs[0].data
```
