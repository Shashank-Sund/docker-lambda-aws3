# Production: the backend behind https://shaismarketpriceeda.com.
#
# The REST API (mgpqvaaqhh) was built by hand in 2023 and is imported, not recreated,
# so its URL (hardcoded in the website) never changes.
#
# Rollout, one reviewed plan at a time:
#   1. adopt:    image_tag = "", use_legacy_lambda = true
#                imports the API unchanged, still calling the 2023 Lambda
#   2. switch:   image_tag = <tested commit>, use_legacy_lambda = false
#                creates stock-eda-prod and points the API at it
#   rollback:    use_legacy_lambda = true (keeps the new function, calls the old one)

terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "6.68.0"
    }
  }

  backend "s3" {
    bucket       = "stock-eda-tfstate-733538815818"
    key          = "prod/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  region = "us-east-1"

  default_tags {
    tags = {
      Project     = "stock-eda"
      Environment = "prod"
      Owner       = "shai"
      ManagedBy   = "terraform"
      Repo        = "docker-lambda-aws3"
    }
  }
}

variable "image_tag" {
  description = "Set by scripts/deploy.sh to the git commit being deployed. Empty means no new function yet."
  type        = string
  default     = ""
}

variable "use_legacy_lambda" {
  description = "Point the API at the 2023 CDK Lambda instead of stock-eda-prod (adoption step and rollback)."
  type        = bool
  default     = true
}

locals {
  api_id           = "mgpqvaaqhh"
  root_resource_id = "7s1xvram25"
  legacy_lambda    = "arn:aws:lambda:us-east-1:733538815818:function:DockerLambdaAws3Stack-DockerFuncF47DA747-nR1zghniM75a"
}

module "backend" {
  source = "../../modules/backend"

  name                   = "stock-eda-prod"
  api_name               = "dockerlambda"
  image_tag              = var.image_tag
  integration_invoke_arn = var.use_legacy_lambda ? "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/${local.legacy_lambda}/invocations" : null
  max_concurrency        = 5
  throttle_rate          = 5
  throttle_burst         = 10
}

import {
  to = module.backend.aws_api_gateway_rest_api.this[0]
  id = local.api_id
}
import {
  to = module.backend.aws_api_gateway_method.post[0]
  id = "${local.api_id}/${local.root_resource_id}/POST"
}
import {
  to = module.backend.aws_api_gateway_method_response.post_200[0]
  id = "${local.api_id}/${local.root_resource_id}/POST/200"
}
import {
  to = module.backend.aws_api_gateway_integration.post[0]
  id = "${local.api_id}/${local.root_resource_id}/POST"
}
import {
  to = module.backend.aws_api_gateway_integration_response.post_200[0]
  id = "${local.api_id}/${local.root_resource_id}/POST/200"
}
import {
  to = module.backend.aws_api_gateway_method.options[0]
  id = "${local.api_id}/${local.root_resource_id}/OPTIONS"
}
import {
  to = module.backend.aws_api_gateway_method_response.options_200[0]
  id = "${local.api_id}/${local.root_resource_id}/OPTIONS/200"
}
import {
  to = module.backend.aws_api_gateway_integration.options[0]
  id = "${local.api_id}/${local.root_resource_id}/OPTIONS"
}
import {
  to = module.backend.aws_api_gateway_integration_response.options_200[0]
  id = "${local.api_id}/${local.root_resource_id}/OPTIONS/200"
}
import {
  to = module.backend.aws_api_gateway_stage.this[0]
  id = "${local.api_id}/Prod"
}

output "api_url" {
  value = module.backend.api_url
}

output "repository_url" {
  value = module.backend.repository_url
}
