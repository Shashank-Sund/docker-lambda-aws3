variable "name" {
  description = "Name for every resource in this environment, for example stock-eda-staging."
  type        = string
}

variable "image_tag" {
  description = "Image tag in this environment's ECR repository. Empty creates only the repository (first run, before an image exists)."
  type        = string
  default     = ""
}

variable "memory_mb" {
  type    = number
  default = 1024
}

variable "timeout_seconds" {
  description = "API Gateway stops waiting at 29 seconds, so a longer Lambda timeout only wastes compute."
  type        = number
  default     = 30
}

variable "max_concurrency" {
  description = "Reserved concurrency: the most copies of the function that can run at once."
  type        = number
  default     = 5
}

variable "stage_name" {
  type    = string
  default = "Prod"
}

variable "allowed_origin" {
  description = "Value of Access-Control-Allow-Origin."
  type        = string
  default     = "*"
}

variable "throttle_rate" {
  description = "Steady-state requests per second allowed by API Gateway."
  type        = number
  default     = 2
}

variable "throttle_burst" {
  type    = number
  default = 5
}

variable "log_retention_days" {
  type    = number
  default = 30
}

variable "force_delete_images" {
  description = "Allow terraform destroy to delete the repository even when it holds images (true for staging only)."
  type        = bool
  default     = false
}

variable "api_name" {
  description = "REST API name. Defaults to name; set it when adopting an existing API so it is not renamed."
  type        = string
  default     = null
}

variable "integration_invoke_arn" {
  description = "Invoke ARN of a different Lambda for the POST integration (rollback switch). Null uses this environment's function."
  type        = string
  default     = null
}
