# EKS and MLflow setup

Create EKS, install MLflow with a PVC, and expose its endpoint for CI. Run commands from the repository root in **PowerShell**. We pin Helm chart **1.6.3** and MLflow **3.4.0**, following the chart's [PVC guide](https://community-charts.github.io/docs/charts/mlflow/basic-installation).

## 1. Prerequisites

Install AWS CLI v2, a current `eksctl`, a compatible `kubectl`, Helm 3 and Python 3.10. Activate `.venv` and install the project's requirements. Your AWS identity needs EKS, EC2/VPC, CloudFormation and IAM provisioning permissions, not only S3 permissions.

```powershell
$env:AWS_PROFILE = "churnlab"
$env:AWS_REGION = "ap-south-1"
$env:AWS_DEFAULT_REGION = $env:AWS_REGION
$env:AWS_ACCOUNT_ID = aws sts get-caller-identity --query Account --output text
aws sts get-caller-identity
```

## 2. Create EKS

Skip cluster creation if reusing a compatible EC2-backed EKS cluster. The configuration targets standard managed nodes, not EKS Auto Mode or Fargate.

Open `eks-cluster-and-mlflow-setup/cluster.yaml` and edit the values directly:

- `metadata.version` is set to `1.35`. Verify it is still in [EKS standard support](https://docs.aws.amazon.com/eks/latest/userguide/kubernetes-versions.html) and supported by your installed eksctl/kubectl.
- Replace `YOUR_PUBLIC_IP/32` under `vpc.publicAccessCIDRs` with your workstation's actual public IPv4 address followed by `/32`. For example, `203.0.113.10/32` shows the format only; do not use that example address.

Then use the same file directly:

```powershell
eksctl create cluster -f eks-cluster-and-mlflow-setup/cluster.yaml --dry-run
eksctl create cluster -f eks-cluster-and-mlflow-setup/cluster.yaml
aws eks update-kubeconfig --name mlops-practice --region $env:AWS_REGION
kubectl get nodes
kubectl create namespace mlflow
```

`--dry-run` previews the configuration; the next command creates the resources. The cluster uses one `t3.medium` worker, a 20Gi root disk and no NAT gateway. Update `publicAccessCIDRs` if your public IP changes. Skip namespace creation if it already exists.

## 3. Install EBS CSI driver and create the PVC

The EBS CSI controller needs an IAM role to provision volumes. If the add-on is already installed and authorized, reuse it and skip role/add-on creation. Otherwise:

```powershell
eksctl create iamserviceaccount --cluster mlops-practice --region $env:AWS_REGION --namespace kube-system --name ebs-csi-controller-sa --role-name MlopsEbsCsiRole --role-only --attach-policy-arn arn:aws:iam::aws:policy/AmazonEBSCSIDriverPolicyV2 --approve
aws eks create-addon --cluster-name mlops-practice --region $env:AWS_REGION --addon-name aws-ebs-csi-driver --service-account-role-arn "arn:aws:iam::${env:AWS_ACCOUNT_ID}:role/MlopsEbsCsiRole"
aws eks wait addon-active --cluster-name mlops-practice --region $env:AWS_REGION --addon-name aws-ebs-csi-driver
kubectl get pods -n kube-system -l app=ebs-csi-controller
kubectl apply -f eks-cluster-and-mlflow-setup/storage.yaml
kubectl get pvc mlflow-data -n mlflow
```

`mlflow-data` can stay **Pending** until the MLflow pod is scheduled in step 4. `WaitForFirstConsumer` ensures the EBS volume is created in the pod's availability zone. This is expected; do not wait for the PVC to bind before installing MLflow.

## 4. Create credentials and install MLflow

The helper prompts for the initial administrator login and creates a Kubernetes Secret without saving passwords to the repository:

```powershell
python eks-cluster-and-mlflow-setup/create_secret.py
helm repo add community-charts https://community-charts.github.io/helm-charts
helm repo update
helm upgrade --install mlflow community-charts/mlflow --version 1.6.3 --namespace mlflow -f eks-cluster-and-mlflow-setup/values.yaml --wait --timeout 10m
kubectl get pods,pvc,svc -n mlflow
```

## 5. Access the UI

```powershell
kubectl port-forward -n mlflow deployment/mlflow 5000:5000
```

Leave the terminal open, visit **http://localhost:5000**, and log in with the credentials from step 4. Stop with Ctrl+C. This checks laptop access before exposing MLflow. After step 7, both your browser and CI use the public NLB URL. Data persists across pod restarts while the PVC is retained.

## 6. Install AWS Load Balancer Controller

Complete steps 6 and 7 before running CI.

```powershell
Invoke-WebRequest https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/v2.14.1/docs/install/iam_policy.json -OutFile eks-cluster-and-mlflow-setup/lbc-policy.local.json
aws iam create-policy --policy-name MlopsLoadBalancerController --policy-document file://eks-cluster-and-mlflow-setup/lbc-policy.local.json
eksctl create iamserviceaccount --cluster mlops-practice --region $env:AWS_REGION --namespace kube-system --name aws-load-balancer-controller --role-name MlopsLoadBalancerControllerRole --attach-policy-arn "arn:aws:iam::${env:AWS_ACCOUNT_ID}:policy/MlopsLoadBalancerController" --approve
$env:EKS_VPC_ID = aws eks describe-cluster --name mlops-practice --region $env:AWS_REGION --query cluster.resourcesVpcConfig.vpcId --output text
helm repo add eks https://aws.github.io/eks-charts
helm repo update
helm upgrade --install aws-load-balancer-controller eks/aws-load-balancer-controller --version 1.14.1 --namespace kube-system --set clusterName=mlops-practice --set serviceAccount.create=false --set serviceAccount.name=aws-load-balancer-controller --set region=$env:AWS_REGION --set vpcId=$env:EKS_VPC_ID --set replicaCount=1 --wait --timeout 10m
kubectl get deployment aws-load-balancer-controller -n kube-system
```

## 7. Create the public LoadBalancer

For this practice lab, expose MLflow through a public NLB on port **5000**. Keep MLflow authentication enabled in `values.yaml` and create the `mlflow-auth` Secret in step 4. HTTP does not encrypt credentials or model traffic; this endpoint is for the practice lab.

```powershell
helm upgrade --install mlflow community-charts/mlflow --version 1.6.3 --namespace mlflow -f eks-cluster-and-mlflow-setup/values.yaml -f eks-cluster-and-mlflow-setup/loadbalancer.values.yaml --wait --timeout 10m
kubectl get service mlflow -n mlflow --watch
```

Wait for `EXTERNAL-IP` to show an AWS DNS name, then stop watching with Ctrl+C:

```powershell
$mlflowEndpoint = kubectl get service mlflow -n mlflow -o jsonpath='{.status.loadBalancer.ingress[0].hostname}'
Write-Output "MLflow URL: http://${mlflowEndpoint}:5000"
kubectl describe service mlflow -n mlflow
```

Continue with [GitHub Actions setup in the main README](../README.md#github-actions-ci) to configure repository variables and IAM user/MLflow secrets, then run training CI.
