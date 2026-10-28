# The 2023 CDK Lambda (backup)

Before Phase 1 the site's API called `DockerLambdaAws3Stack-DockerFuncF47DA747-nR1zghniM75a`, deployed by
the CDK stack `DockerLambdaAws3Stack` (created 2023-09-07, last updated 2023-09-24). The API now calls
`stock-eda-prod` (Terraform). This folder keeps what is needed to bring the old function back.

## What is backed up

| What | Where |
| --- | --- |
| Container image, byte for byte | ECR `stock-eda-legacy-backup:cdk-2023-09-23`, digest `sha256:2bf557dcb395cbca9908b2e0cbcd8770023a07ebd7938d90ce8ab6f9e514f35a` (905 MB). The tag is immutable and the repository has no lifecycle policy. |
| Function settings | `function-configuration.json`: arm64, 1024 MB, 60 s timeout, no environment variables |
| Public function URL settings | `function-url.json` (auth `NONE`) |
| Who could invoke it | `resource-policy.json`: the function URL and API Gateway |
| IAM role | `iam-role.json`: `AWSLambdaBasicExecutionRole` and `AmazonS3FullAccess` (the S3 policy was never needed) |
| CloudFormation template | `cloudformation-template.json` |
| Source code | git tag `cdk-legacy-2023` (commit df55fc5, committed 4 minutes after the image was deployed) |

The copy was checked on 2026-10-28: its digest and size match the original, and it runs locally under the
Lambda emulator. Note that, like the original, it no longer returns charts: its 2023 yfinance version gets
empty data from Yahoo and the handler fails on the empty table. That is the bug Phase 1 fixed.

## Restore

Only needed to inspect or rerun the old code. To roll back the live site, deploy an earlier
`stock-eda-prod` image instead (`scripts/deploy.sh prod plan` from that commit).

```sh
# 1. A role the function can run as (logs only; it does not need S3)
aws iam create-role --role-name stock-eda-legacy-restore \
  --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
aws iam attach-role-policy --role-name stock-eda-legacy-restore \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# 2. The function, from the backup image (wait ~10 s after creating the role)
aws lambda create-function --function-name stock-eda-legacy-restore --package-type Image \
  --code ImageUri=733538815818.dkr.ecr.us-east-1.amazonaws.com/stock-eda-legacy-backup:cdk-2023-09-23 \
  --architectures arm64 --memory-size 1024 --timeout 60 \
  --role arn:aws:iam::733538815818:role/stock-eda-legacy-restore

# 3. Or run it locally, no AWS compute
docker run --rm -p 9001:8080 733538815818.dkr.ecr.us-east-1.amazonaws.com/stock-eda-legacy-backup:cdk-2023-09-23
curl -XPOST localhost:9001/2015-03-31/functions/function/invocations \
  -d '{"start_date":"2025-01-02","end_date":"2025-06-30","symbol":"AAPL"}'
```

The CDK code is also kept at the tag (`git checkout cdk-legacy-2023`). Redeploying it with `npx cdk deploy`
has not been tested and would create a new function URL.
