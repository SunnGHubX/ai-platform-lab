variable "vpc_cidr" {
  description = "VPC /16. Keep non-overlapping across envs so you can peer / Transit-Gateway them later."
  type        = string
}

variable "az_count" {
  description = "Number of AZs."
  type        = number
}

variable "single_nat_gateway" {
  description = "One shared NAT (dev/staging) vs one per AZ (prod)."
  type        = bool
}

variable "enable_interface_endpoints" {
  description = "Private interface endpoints for ECR/STS/logs/SSM/Secrets Manager."
  type        = bool
}

variable "flow_log_retention_days" {
  description = "VPC flow log retention."
  type        = number
}
