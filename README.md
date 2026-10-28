# docker-lambda-aws3 Back-end 

https://shaismarketpriceeda.com/

This tool is used to conduct Exploratory Data Analysis on historical stock price data of a given ticker, start_date, and end_date. These visualizations and plots can be used to derive insights on market price data using the scikit-learn library. This backend code was deployed on a containerized lambda through AWS-CLI and AWS-CDK. The lambda is activated through an API Gateway url, which then takes in a json input through a post request. The json input data is then used to send an API request through the yfinance python library, which retrieves the data and visualizes it in various graphs through the matplotlib library. These graphs can be used to analyze and derive insights on the market price data much more effectively. 

The tool allows for both single-stock and multi-stock analysis. The current visualizations for a single stock allow the user to highlight the the closing stock prices over any given period of time, correlation between the stock prices, distribution of closing stock prices, and daily returns of the stock. For the multi-stock analysis, the user can view the closing stock price for multiple companies over time. More functionality will be added.

**IMPORTANT NOTE: This visualization tool may only support certain tickers in which stocks available may be limited per their library guidelines.**

# Architecture

![StockPriceAnalysisArchitecture drawio (2)](https://github.com/Shashank-Sund/docker-lambda-aws3/assets/29733360/cb3ad8a7-a0cc-40cf-afc1-c85786114be1)

# Back-End Tools

AWS Tools : Lambda (container image), API Gateway, ECR, CloudWatch Logs, Terraform

Libraries: yfinance, pandas, matplotlib, seaborn

Languages: Python, HCL

Other tools: Docker, pytest, GitHub Actions

# Repository layout

| Path | What it is |
|---|---|
| `image/` | The Lambda: `src/main.py`, pinned `requirements.txt`, `Dockerfile` (Python 3.13 Lambda base, plus a `test` stage) |
| `image/tests/` | pytest suite with fake Yahoo data (offline) and one `live` test against real Yahoo |
| `scripts/test.sh` | Runs the tests inside the Lambda OS and packages |
| `scripts/smoke.sh` | Runs the real image locally in the Lambda emulator (read-only filesystem, like Lambda) and sends the website's requests; with a URL argument it tests a deployed API instead |
| `scripts/deploy.sh` | Builds the image for the current commit, pushes it to ECR, and plans or applies Terraform |
| `terraform/bootstrap/` | One-time: the S3 bucket holding Terraform state |
| `terraform/modules/backend/` | One environment: ECR repository, Lambda, log group, REST API |
| `terraform/envs/staging/`, `terraform/envs/prod/` | The two environments, each with its own state |
| `bin/`, `lib/`, `cdk.json` | The original 2023 CDK app (legacy; still running the old Lambda until it is retired) |

# Test locally

Requires Docker.

```bash
scripts/test.sh            # unit tests, offline
scripts/test.sh -m live    # one test against real Yahoo Finance
scripts/smoke.sh           # real image in the Lambda emulator, real data
```

GitHub Actions runs the unit tests on every pull request.

# Deploy with Terraform

Requires Terraform, Docker and the AWS CLI. Every resource is tagged `Project=stock-eda`, `Environment`, `Owner`, `ManagedBy=terraform`, `Repo`.

```bash
scripts/deploy.sh staging plan     # build and push the image, show the plan
scripts/deploy.sh staging apply    # apply exactly that plan, then send a warm-up request
scripts/smoke.sh "$(terraform -chdir=terraform/envs/staging output -raw api_url)"
```

The image tag is the git commit, so a deploy always maps to exact code, and nothing is applied without a printed plan. The first start after a new image can take over 10 seconds while Lambda fetches it; the warm-up request absorbs that.

Production keeps the original API URL (the website calls it directly): `terraform/envs/prod` imports that API instead of creating one. To roll production back to the 2023 Lambda, apply prod with `-var use_legacy_lambda=true`.

# Sources

Stock Market EDA - https://medium.com/mlearning-ai/exploratory-data-analysis-on-stock-market-data-5d99fbdf3b04

Alpaca API in code use - https://levelup.gitconnected.com/how-to-build-an-aws-lambda-for-algorithmic-trading-da5d6826551a

Alpaca API docs - https://alpaca.markets/docs/clients/
                - https://github.com/alpacahq/alpaca-py

Yfinance troubleshooting - https://stackoverflow.com/questions/76697648/python-aws-cdk-build-broke-yesterday-please-make-sure-the-libxml2-and-libxslt
                         - https://stackoverflow.com/questions/68767280/lambda-docker-base-unable-to-install-matplotlib


   
