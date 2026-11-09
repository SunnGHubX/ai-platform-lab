variable "name" {
  description = "VPC name."
  type        = string
}

variable "region" {
  description = "AWS region (for endpoint service names)."
  type        = string
}

variable "cidr" {
  description = "VPC CIDR. Must be a /16 so the subnet carving in main.tf works."
  type        = string

  validation {
    condition     = can(cidrnetmask(var.cidr)) && endswith(var.cidr, "/16")
    error_message = "cidr must be a valid /16, e.g. 10.10.0.0/16."
  }
}

variable "az_count" {
  description = "Number of AZs (EKS needs at least 2)."
  type        = number
  default     = 3

  validation {
    condition     = var.az_count >= 2 && var.az_count <= 3
    error_message = "az_count must be 2 or 3."
  }
}

variable "single_nat_gateway" {
  description = "true = one shared NAT (cheap, single point of failure); false = one per AZ."
  type        = bool
  default     = true
}

variable "enable_interface_endpoints" {
  description = "Create interface VPC endpoints (ECR, STS, logs, SSM, Secrets Manager)."
  type        = bool
  default     = false
}

variable "flow_log_retention_days" {
  description = "VPC flow log retention in CloudWatch."
  type        = number
  default     = 30
}

variable "cluster_name" {
  description = "EKS cluster name, used for subnet discovery tags."
  type        = string
}

variable "tags" {
  description = "Extra tags."
  type        = map(string)
  default     = {}
}
