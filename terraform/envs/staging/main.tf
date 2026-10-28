# Staging: a separate copy of the backend for testing. It shares nothing with the
# live site (own repository, function, API and state file).

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
    key          = "staging/terraform.tfstate"
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
      Environment = "staging"
      Owner       = "shai"
      ManagedBy   = "terraform"
      Repo        = "docker-lambda-aws3"
    }
  }
}

variable "image_tag" {
  description = "Set by scripts/deploy.sh to the git commit being deployed."
  type        = string
  default     = ""
}

module "backend" {
  source = "../../modules/backend"

  name                = "stock-eda-staging"
  image_tag           = var.image_tag
  max_concurrency     = 2
  force_delete_images = true
}

output "api_url" {
  value = module.backend.api_url
}

output "repository_url" {
  value = module.backend.repository_url
}
