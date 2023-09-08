# docker-lambda-aws3 Back-end 

This tool is used to conduct Exploratory Data Analysis on historical stock price data of a given ticker, start_date, and end_date. These visualizations and plots can be used to derive ingights on market price data using the scikit-learn library. This repo also contains all of the backend code for the Dashboard application.

# Architecture

![StockPriceAnalysisArchitecture drawio (2)](https://github.com/Shashank-Sund/docker-lambda-aws3/assets/29733360/cb3ad8a7-a0cc-40cf-afc1-c85786114be1)

# Tools

AWS Tools : AWS-CDK, AWS-CLI, ECR, Cloud Formation, Lambda, S3, API Gateway, CloudFront, Route 53

Libraries: alpaca-py, pandas, matplotlib, plotly, seaborn, scikit-learn

Languages: Python, Javascript

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

  1. cd Stock-Price-Analysis
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

   
