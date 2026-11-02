# Set up S3 data versioning with DVC

Run these commands from the root of your clone in PowerShell. You need Python 3.10, Git, an S3 bucket, and AWS credentials with access to that bucket.

## Dataset and DVC files

`examples/churn.csv` is the public starter: 3,000 synthetic customer records generated with seed 42. Copy it to `data/churn.csv` for training. Git tracks the starter and `data/churn.csv.dvc`; DVC stores the working dataset in S3.

| Column | Meaning |
| --- | --- |
| `tenure_months` | Customer tenure in months |
| `monthly_charges` | Synthetic monthly charge in arbitrary currency units |
| `support_calls` | Support call count |
| `month_to_month` | 1 for a month-to-month contract; otherwise 0 |
| `churn` | Binary target: 1 means churn |

## 1. Prepare the environment and dataset

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item examples/churn.csv data/churn.csv
```

Create the environment once and activate it in new terminals. Skip the copy if you already have working data you want to keep. If PowerShell blocks activation, use `.\.venv\Scripts\python.exe -m pip` and `.\.venv\Scripts\dvc.exe` instead of `python -m pip` and `dvc`. On macOS/Linux, activate with `source .venv/bin/activate` and copy the starter with `cp examples/churn.csv data/churn.csv`.

## 2. Authenticate with AWS

Install AWS CLI v2 separately if needed. Use an IAM user's access key ID and secret access key with permission to access your S3 bucket; do not use root-account keys.

Create a local profile named `churnlab`:

```powershell
aws configure --profile churnlab
```

Enter the following at the prompts:

- AWS access key ID: your IAM user's access key ID.
- AWS secret access key: its matching secret key.
- Default region name: your bucket's region, for example `ap-south-1`.
- Default output format: `json`.

Select the profile for DVC and verify access to your AWS identity:

```powershell
$env:AWS_PROFILE = "churnlab"
aws sts get-caller-identity
```

This profile is for local use. For GitHub training CI, save the same IAM user access keys as repository secrets as described in [the main README](../README.md#github-actions-ci). The uploader needs bucket listing and object read/write access to the DVC prefix, plus applicable KMS permissions for a customer-managed encryption key.

## 3. Upload with DVC

Replace `YOUR_BUCKET` with your bucket name:

```powershell
dvc remote add --local -f storage s3://YOUR_BUCKET/dvc-cache
dvc add data/churn.csv
dvc push data/churn.csv.dvc -r storage
```

`dvc add` updates the dataset pointer; `dvc push` uploads the data in DVC's cache layout. The local remote configuration stays in the ignored `.dvc/config.local` file.

## 4. Commit dataset changes

After uploading, check the pointer:

```powershell
git diff -- data/churn.csv.dvc
```

If it changed, commit and push it:

```powershell
git add data/churn.csv.dvc
git commit -m "Update churn dataset version"
git push
```

The initial starter upload may leave the pointer unchanged; then no commit is needed. For later dataset updates, repeat `dvc add`, `dvc push`, and the pointer commit. Keep older DVC objects in S3 if you need to retrieve earlier versions.

To run S3 training in CI, complete the [GitHub Actions setup](../README.md#github-actions-ci).
