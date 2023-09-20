# docker-lambda-aws3 Back-end 

This tool is used to conduct Exploratory Data Analysis on historical stock price data of a given ticker, start_date, and end_date. These visualizations and plots can be used to derive insights on market price data using the scikit-learn library. This backend code was deployed on a containerized lambda through AWS-CLI and AWS-CDK. The lambda is activated through an API Gateway url, which then takes in a json input through a post request. The json input data is then used to send an API request through the yfinance python library, which retrieves the data and visualizes it in various graphs through the matplotlib library. These graphs can be used to analyze and derive insights on the market price data much more effectively. 

The tool allows for both single-stock and multi-stock analysis. The current visualizations for a single stock allow the user to highlight the the closing stock prices over any given period of time, correlation between the stock prices, distribution of closing stock prices, and daily returns of the stock. For the multi-stock analysis, the user can view the closing stock price for multiple companies over time. More functionality will be added.

**IMPORTANT NOTE: This visualization tool may only support certain tickers in which stocks available may be limited per their library guidelines.**

# Architecture

![StockPriceAnalysisArchitecture drawio (2)](https://github.com/Shashank-Sund/docker-lambda-aws3/assets/29733360/cb3ad8a7-a0cc-40cf-afc1-c85786114be1)

# Back-End Tools

AWS Tools : AWS-CDK, AWS-CLI, ECR, Cloud Formation, Lambda

Libraries: yfinance, pandas, matplotlib, plotly, seaborn, scikit-learn

Languages: Python, Typescript

Other tools: Docker

# Setup

1. Please ensure python version 3.11< is installed via anaconda
2. Download and install Docker to your local
3. Download and install AWS-CLI
   - Setup AWS-CLI by creating an IAM Access Key for your AWS user account
   - Configure CLI through 'aws configure' command
4. Clone repo to your local
5. Run startup.sh in local terminal


# Test locally in terminal

  1. cd image
  2. docker build -t docker-image:test .
     - builds image
  3. docker run -p 9000:8080 docker-image:test
     - runs image in container
  4. Send a curl request to the url outputted from the step above

# Deploy to AWS (in terminal)

  1. cd docker-lambda-aws3
  2. cdk bootstrap
     - bootstraps environment
  4. cdk deploy
     - deploys resources in console

# Welcome to your CDK TypeScript project

This is a blank project for CDK development with TypeScript.

The `cdk.json` file tells the CDK Toolkit how to execute your app.

## Useful commands

* `npm run build`   compile typescript to js
* `npm run watch`   watch for changes and compile
* `npm run test`    perform the jest unit tests
* `cdk deploy`      deploy this stack to your default AWS account/region
* `cdk diff`        compare deployed stack with current state
* `cdk synth`       emits the synthesized CloudFormation template

# Sources

Stock Market EDA - https://medium.com/mlearning-ai/exploratory-data-analysis-on-stock-market-data-5d99fbdf3b04

Alpaca API in code use - https://levelup.gitconnected.com/how-to-build-an-aws-lambda-for-algorithmic-trading-da5d6826551a

Alpaca API docs - https://alpaca.markets/docs/clients/
                - https://github.com/alpacahq/alpaca-py

Yfinance troubleshooting - https://stackoverflow.com/questions/76697648/python-aws-cdk-build-broke-yesterday-please-make-sure-the-libxml2-and-libxslt
                         - https://stackoverflow.com/questions/68767280/lambda-docker-base-unable-to-install-matplotlib


   
