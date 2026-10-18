variable "region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "us-east-1"
}

variable "name" {
  description = "Base name of the function and its resources."
  type        = string
  default     = "juris-bridge-mcp"
}

variable "environment" {
  description = "Suffix that separates deployments in one account."
  type        = string
  default     = "prod"
}

variable "image_tag" {
  description = "Tag of the image pushed to the ECR repository."
  type        = string
  default     = "latest"
}

variable "architecture" {
  description = "Lambda architecture; must match the platform the image was built for."
  type        = string
  default     = "arm64"

  validation {
    condition     = contains(["arm64", "x86_64"], var.architecture)
    error_message = "architecture must be arm64 or x86_64."
  }
}

variable "memory_mb" {
  type    = number
  default = 512
}

variable "timeout_seconds" {
  type    = number
  default = 60
}

variable "api_keys" {
  description = "Comma-separated Bearer keys the server accepts."
  type        = string
  sensitive   = true
}

variable "datajud_api_key" {
  description = "DataJud API key (the CNJ public key)."
  type        = string
  sensitive   = true
}

variable "commit_hash" {
  description = "Commit stamped on every wide event."
  type        = string
  default     = "unknown"
}

variable "extra_environment" {
  description = "Further JURIS_BRIDGE_* settings, passed through as Lambda environment variables."
  type        = map(string)
  default     = {}
}
