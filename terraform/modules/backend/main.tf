# The stock EDA backend for one environment: image repository, Lambda, logs, and a
# REST API configured like the original hand-built one (non-proxy Lambda
# integration, mock OPTIONS for CORS), so the website's requests behave the same.

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "6.68.0"
    }
  }
}

# ---------- image repository ----------

resource "aws_ecr_repository" "this" {
  name                 = var.name
  image_tag_mutability = "IMMUTABLE"
  force_delete         = var.force_delete_images

  image_scanning_configuration {
    scan_on_push = true
  }
}

# Keep the 10 newest images; older ones are rollback history nobody needs.
resource "aws_ecr_lifecycle_policy" "this" {
  repository = aws_ecr_repository.this.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "keep the 10 newest images"
      selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 10 }
      action       = { type = "expire" }
    }]
  })
}

# ---------- Lambda ----------

resource "aws_iam_role" "lambda" {
  name = "${var.name}-lambda"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "logs" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Created before the function so Lambda does not create one with no expiry.
resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.name}"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "this" {
  count = var.image_tag == "" ? 0 : 1

  function_name = var.name
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.this.repository_url}:${var.image_tag}"
  architectures = ["arm64"]
  memory_size   = var.memory_mb
  timeout       = var.timeout_seconds

  # Caps concurrent runs so a burst of traffic cannot run up cost.
  reserved_concurrent_executions = var.max_concurrency

  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.lambda.name
  }

  depends_on = [aws_iam_role_policy_attachment.logs]
}

# ---------- REST API ----------

# The API exists once there is a function to call: this environment's own, or the
# one named by integration_invoke_arn (used to adopt an existing API unchanged).
resource "aws_api_gateway_rest_api" "this" {
  count = var.image_tag != "" || var.integration_invoke_arn != null ? 1 : 0

  name = coalesce(var.api_name, var.name)
  endpoint_configuration {
    types = ["EDGE"]
  }
}

locals {
  api          = one(aws_api_gateway_rest_api.this[*])
  fn           = one(aws_lambda_function.this[*])
  cors_headers = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
  allow_origin = "'${var.allowed_origin}'"
}

resource "aws_api_gateway_method" "post" {
  count         = local.api == null ? 0 : 1
  rest_api_id   = local.api.id
  resource_id   = local.api.root_resource_id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "post" {
  count                   = local.api == null ? 0 : 1
  rest_api_id             = local.api.id
  resource_id             = local.api.root_resource_id
  http_method             = aws_api_gateway_method.post[0].http_method
  type                    = "AWS"
  integration_http_method = "POST"
  # Normally this environment's function; set integration_invoke_arn to roll back.
  uri                  = coalesce(var.integration_invoke_arn, try(local.fn.invoke_arn, null))
  passthrough_behavior = "WHEN_NO_MATCH"
  content_handling     = "CONVERT_TO_TEXT"
}

resource "aws_api_gateway_method_response" "post_200" {
  count       = local.api == null ? 0 : 1
  rest_api_id = local.api.id
  resource_id = local.api.root_resource_id
  http_method = aws_api_gateway_method.post[0].http_method
  status_code = "200"
  # Matches the original API: responses go out with Content-Type text/html.
  response_models = { "text/html" = "Empty" }
  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin" = false
  }
}

resource "aws_api_gateway_integration_response" "post_200" {
  count             = local.api == null ? 0 : 1
  rest_api_id       = local.api.id
  resource_id       = local.api.root_resource_id
  http_method       = aws_api_gateway_method.post[0].http_method
  status_code       = aws_api_gateway_method_response.post_200[0].status_code
  selection_pattern = ""
  response_parameters = {
    "method.response.header.Access-Control-Allow-Origin" = local.allow_origin
  }
  depends_on = [aws_api_gateway_integration.post]
}

resource "aws_api_gateway_method" "options" {
  count         = local.api == null ? 0 : 1
  rest_api_id   = local.api.id
  resource_id   = local.api.root_resource_id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options" {
  count             = local.api == null ? 0 : 1
  rest_api_id       = local.api.id
  resource_id       = local.api.root_resource_id
  http_method       = aws_api_gateway_method.options[0].http_method
  type              = "MOCK"
  request_templates = { "application/json" = "{\"statusCode\": 200}" }
}

resource "aws_api_gateway_method_response" "options_200" {
  count           = local.api == null ? 0 : 1
  rest_api_id     = local.api.id
  resource_id     = local.api.root_resource_id
  http_method     = aws_api_gateway_method.options[0].http_method
  status_code     = "200"
  response_models = { "application/json" = "Empty" }
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = false
    "method.response.header.Access-Control-Allow-Methods" = false
    "method.response.header.Access-Control-Allow-Origin"  = false
  }
}

resource "aws_api_gateway_integration_response" "options_200" {
  count       = local.api == null ? 0 : 1
  rest_api_id = local.api.id
  resource_id = local.api.root_resource_id
  http_method = aws_api_gateway_method.options[0].http_method
  status_code = aws_api_gateway_method_response.options_200[0].status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = local.cors_headers
    "method.response.header.Access-Control-Allow-Methods" = "'OPTIONS,POST'"
    "method.response.header.Access-Control-Allow-Origin"  = local.allow_origin
  }
  depends_on = [aws_api_gateway_integration.options]
}

# Errors API Gateway makes itself (throttled, over the Lambda's concurrency cap, timed out)
# skip the integration response, so without these they have no CORS header and the browser
# reports a network failure instead of letting the page see the status.
resource "aws_api_gateway_gateway_response" "cors" {
  for_each      = local.api == null ? toset([]) : toset(["DEFAULT_4XX", "DEFAULT_5XX"])
  rest_api_id   = local.api.id
  response_type = each.key
  response_parameters = {
    "gatewayresponse.header.Access-Control-Allow-Origin" = local.allow_origin
  }
}

resource "aws_api_gateway_deployment" "this" {
  count       = local.api == null ? 0 : 1
  rest_api_id = local.api.id

  # Redeploy when any method, response or integration changes. Listing them here
  # also orders the deployment after them, so the snapshot includes the change.
  triggers = {
    redeploy = sha1(jsonencode([
      aws_api_gateway_method.post[0],
      aws_api_gateway_method_response.post_200[0],
      aws_api_gateway_integration.post[0],
      aws_api_gateway_integration_response.post_200[0],
      aws_api_gateway_method.options[0],
      aws_api_gateway_method_response.options_200[0],
      aws_api_gateway_integration.options[0],
      aws_api_gateway_integration_response.options_200[0],
      aws_api_gateway_gateway_response.cors,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "this" {
  count         = local.api == null ? 0 : 1
  rest_api_id   = local.api.id
  deployment_id = aws_api_gateway_deployment.this[0].id
  stage_name    = var.stage_name
}

# Rate limit for every method on the stage.
resource "aws_api_gateway_method_settings" "throttle" {
  count       = local.api == null ? 0 : 1
  rest_api_id = local.api.id
  stage_name  = aws_api_gateway_stage.this[0].stage_name
  method_path = "*/*"
  settings {
    throttling_rate_limit  = var.throttle_rate
    throttling_burst_limit = var.throttle_burst
  }
}

resource "aws_lambda_permission" "api" {
  count         = local.api == null || local.fn == null ? 0 : 1
  statement_id  = "AllowApiGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = local.fn.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${local.api.execution_arn}/*/POST/"
}
