# Symlinked into every stack: the variables every environment must set, and the tagging standard.
# Each stack defines `local.stack` in its own main.tf.

variable "project" {
  description = "Project slug used in names, tags and SSM paths."
  type        = string
  default     = "ai-platform"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,20}$", var.project))
    error_message = "project must be 3-21 chars of lowercase letters, digits and dashes."
  }
}

variable "environment" {
  description = "Deployment environment."
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

variable "region" {
  description = "AWS region."
  type        = string
}

variable "account_id" {
  description = "AWS account this environment lives in. The provider refuses to run against any other account."
  type        = string

  validation {
    condition     = can(regex("^[0-9]{12}$", var.account_id))
    error_message = "account_id must be a 12-digit AWS account ID."
  }
}

variable "assume_role_arn" {
  description = "Role to assume in the target account (CI sets this; leave null to use your own credentials)."
  type        = string
  default     = null
}

variable "owner" {
  description = "Team or person accountable for these resources (tag)."
  type        = string
}

variable "cost_center" {
  description = "Cost allocation tag."
  type        = string
}

locals {
  name_prefix = "${var.project}-${var.environment}"  # e.g. ai-platform-prod
  ssm_prefix  = "/${var.project}/${var.environment}" # cross-stack contract root

  default_tags = {
    Project     = var.project
    Environment = var.environment
    Stack       = local.stack
    Owner       = var.owner
    CostCenter  = var.cost_center
    ManagedBy   = "terraform"
    Repository  = "SunnGHubX/ai-platform-lab"
  }
}
