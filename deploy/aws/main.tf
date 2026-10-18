terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

locals {
  function_name = "${var.name}-${var.environment}"
  log_group     = "/aws/lambda/${local.function_name}"
}

resource "aws_ecr_repository" "image" {
  name = local.function_name
  # Lets `terraform destroy` remove the repository together with its images.
  force_delete = true
}

resource "aws_cloudwatch_log_group" "function" {
  name              = local.log_group
  retention_in_days = 30
}

resource "aws_iam_role" "function" {
  name = "${local.function_name}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "logs" {
  name = "logs"
  role = aws_iam_role.function.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
      Resource = "${aws_cloudwatch_log_group.function.arn}:*"
    }]
  })
}

resource "aws_lambda_function" "server" {
  function_name = local.function_name
  role          = aws_iam_role.function.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.image.repository_url}:${var.image_tag}"
  architectures = [var.architecture]
  memory_size   = var.memory_mb
  timeout       = var.timeout_seconds

  environment {
    variables = merge(
      {
        JURIS_BRIDGE_SERVER_API_KEYS         = var.api_keys
        JURIS_BRIDGE_DATAJUD_API_KEY         = var.datajud_api_key
        JURIS_BRIDGE_DATAJUD_TIMEOUT_SECONDS = tostring(var.datajud_timeout_seconds)
        JURIS_BRIDGE_LOG_COMMIT_HASH         = var.commit_hash
      },
      var.extra_environment,
    )
  }

  depends_on = [aws_cloudwatch_log_group.function, aws_iam_role_policy.logs]
}

# Auth is NONE at the URL: the Bearer key is checked inside the app (ADR 0003).
resource "aws_lambda_function_url" "server" {
  function_name      = aws_lambda_function.server.function_name
  authorization_type = "NONE"
}

resource "aws_lambda_permission" "public_url" {
  statement_id           = "AllowPublicFunctionUrl"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.server.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

# A Function URL with auth NONE needs both permissions (AWS requires InvokeFunction since Oct 2025).
resource "aws_lambda_permission" "public_invoke" {
  statement_id  = "AllowPublicInvokeFunction"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.server.function_name
  principal     = "*"
}

resource "aws_cloudwatch_query_definition" "slowest_requests" {
  name            = "${local.function_name}/slowest-requests"
  log_group_names = [aws_cloudwatch_log_group.function.name]
  query_string    = <<-EOT
    fields @timestamp, tool.name, source, duration_ms, outcome
    | filter ispresent(duration_ms)
    | sort duration_ms desc
    | limit 50
  EOT
}

resource "aws_cloudwatch_query_definition" "errors" {
  name            = "${local.function_name}/errors"
  log_group_names = [aws_cloudwatch_log_group.function.name]
  query_string    = <<-EOT
    fields @timestamp, tool.name, source, outcome, error.code, http.status
    | filter ispresent(outcome) and outcome != "success"
    | sort @timestamp desc
    | limit 100
  EOT
}

resource "aws_cloudwatch_query_definition" "calls_by_tool" {
  name            = "${local.function_name}/calls-by-tool"
  log_group_names = [aws_cloudwatch_log_group.function.name]
  query_string    = <<-EOT
    filter ispresent(tool.name)
    | stats count() as calls, avg(duration_ms) as avg_ms, pct(duration_ms, 95) as p95_ms by tool.name
    | sort calls desc
  EOT
}

resource "aws_cloudwatch_query_definition" "cold_starts" {
  name            = "${local.function_name}/cold-starts"
  log_group_names = [aws_cloudwatch_log_group.function.name]
  query_string    = <<-EOT
    filter cold_start = 1
    | fields @timestamp, duration_ms, region, version
    | sort @timestamp desc
    | limit 50
  EOT
}
