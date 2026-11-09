variable "project" {
  description = "Project slug."
  type        = string
  default     = "ai-platform"
}

variable "environment" {
  description = "Environment this account hosts."
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev, staging or prod."
  }
}

variable "account_id" {
  description = "Target AWS account ID."
  type        = string
}

variable "region" {
  description = "AWS region."
  type        = string
  default     = "us-west-2"
}

variable "github_repository" {
  description = "owner/repo allowed to assume the CI roles."
  type        = string
  default     = "SunnGHubX/sunn-platform-lab"
}
