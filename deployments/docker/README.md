# Docker model deployment

Flow: **model label -> select evaluated model in MLflow -> download model -> build Docker image -> push to ECR -> deploy to EKS**.

Complete the [CD setup](../README.md), including EKS API access for the runner. In GitHub, choose **Actions -> CD - Docker model to EKS -> Run workflow**, select `main`, and enter a label such as `20261025-3`.

| File | Purpose |
| --- | --- |
| `Dockerfile` | Serves the downloaded model with MLflow on port 8080 |
| `requirements.txt` | Matches training's model-loading dependencies |
| `kubernetes.yaml` | One Deployment and private Service in `inference-docker` |
| `request.json` | Example prediction request |

The image contains the complete MLflow model folder, including `model.pkl`. The running container needs no MLflow credentials or connection. It serves class predictions (0 or 1); it uses the saved classifier's `predict()` method. Evaluation's custom probability threshold is not embedded in the serving model.

After CD succeeds, run:

```powershell
kubectl port-forward -n inference-docker service/churn-docker 8081:80
```

In another terminal, from the repository root:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8081/invocations -ContentType application/json -InFile deployments/docker/request.json
```
