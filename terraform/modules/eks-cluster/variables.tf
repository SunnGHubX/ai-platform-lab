variable "name" {
  description = "Cluster name."
  type        = string
}

variable "kubernetes_version" {
  description = "EKS Kubernetes version (check EKS standard-support calendar before bumping)."
  type        = string
}

variable "vpc_id" {
  description = "VPC ID."
  type        = string
}

variable "private_subnet_ids" {
  description = "Subnets for nodes."
  type        = list(string)
}

variable "intra_subnet_ids" {
  description = "Subnets for control-plane ENIs."
  type        = list(string)
}

variable "endpoint_public_access" {
  description = "Expose the API server publicly (restricted by CIDR). false = VPN/bastion only."
  type        = bool
  default     = false
}

variable "endpoint_public_access_cidrs" {
  description = "CIDRs allowed to reach a public API endpoint."
  type        = list(string)
  default     = []

  validation {
    condition     = !contains(var.endpoint_public_access_cidrs, "0.0.0.0/0")
    error_message = "Do not open the EKS API to 0.0.0.0/0; list your office/VPN CIDRs."
  }
}

variable "enable_creator_admin" {
  description = "Grant the identity running Terraform cluster-admin. Handy in dev; prefer admin_role_arns in prod."
  type        = bool
  default     = false
}

variable "admin_role_arns" {
  description = "IAM role ARNs granted cluster-admin via EKS access entries."
  type        = list(string)
  default     = []
}

variable "system_node_group" {
  description = "Always-on node group for platform add-ons."
  type = object({
    instance_types = list(string)
    min_size       = number
    max_size       = number
  })
}

variable "cpu_node_group" {
  description = "General-purpose CPU node group."
  type = object({
    instance_types = list(string)
    capacity_type  = string
    min_size       = number
    max_size       = number
  })

  validation {
    condition     = contains(["ON_DEMAND", "SPOT"], var.cpu_node_group.capacity_type)
    error_message = "capacity_type must be ON_DEMAND or SPOT."
  }
}

variable "gpu_node_group" {
  description = "Tainted GPU node group for inference (min_size 0 = scale from zero)."
  type = object({
    enabled        = bool
    instance_types = optional(list(string), ["g6.xlarge"])
    capacity_type  = optional(string, "ON_DEMAND")
    min_size       = optional(number, 0)
    max_size       = optional(number, 1)
    gpus_per_node  = optional(number, 1)
    disk_size_gib  = optional(number, 200)
  })
  default = { enabled = false }
}

variable "tags" {
  description = "Extra tags."
  type        = map(string)
  default     = {}
}
