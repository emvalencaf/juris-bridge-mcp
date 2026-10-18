output "mcp_url" {
  description = "The MCP endpoint to give to clients."
  value       = "${aws_lambda_function_url.server.function_url}mcp"
}

output "ecr_repository_url" {
  value = aws_ecr_repository.image.repository_url
}

output "log_group" {
  value = aws_cloudwatch_log_group.function.name
}

output "function_name" {
  value = aws_lambda_function.server.function_name
}
