output "repository_url" {
  value = aws_ecr_repository.this.repository_url
}

output "function_name" {
  value = one(aws_lambda_function.this[*].function_name)
}

output "api_url" {
  description = "The URL the website POSTs to."
  value       = one(aws_api_gateway_stage.this[*].invoke_url)
}
