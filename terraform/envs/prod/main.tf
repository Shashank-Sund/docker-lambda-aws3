# Production: the backend behind https://shaismarketpriceeda.com.
#
# The REST API (mgpqvaaqhh) was built by hand in 2023 and is imported, not recreated,
# so its URL (hardcoded in the website) never changes.
#
# On 2026-10-28 the API was imported unchanged, then pointed at stock-eda-prod; the 2023
# CDK Lambda it used to call was deleted afterwards (backup: legacy-lambda/README.md).
# Rollback: deploy an earlier image, e.g. plan with -var image_tag=<earlier commit>.

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

locals {
  api_id           = "mgpqvaaqhh"
  root_resource_id = "7s1xvram25"
}

module "backend" {
  source = "../../modules/backend"

  name            = "stock-eda-prod"
  api_name        = "dockerlambda"
  image_tag       = var.image_tag
  max_concurrency = 5
  throttle_rate   = 5
  throttle_burst  = 10
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
