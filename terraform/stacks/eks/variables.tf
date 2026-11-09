variable "kubernetes_version" {
  description = "EKS version."
  type        = string
}

variable "endpoint_public_access" {
  description = "Public API endpoint (restricted by CIDR)."
  type        = bool
}

variable "endpoint_public_access_cidrs" {
  description = "CIDRs allowed to the public API endpoint."
  type        = list(string)
  default     = []
}

variable "admin_role_arns" {
  description = "Roles granted cluster-admin (SSO admin role, CI apply role)."
  type        = list(string)
  default     = []
}

variable "system_node_group" {
  description = "System node group sizing."
  type = object({
    instance_types = list(string)
    min_size       = number
    max_size       = number
  })
}

variable "cpu_node_group" {
  description = "CPU node group sizing."
  type = object({
    instance_types = list(string)
    capacity_type  = string
    min_size       = number
    max_size       = number
  })
}

variable "gpu_node_group" {
  description = "GPU node group sizing."
  type = object({
    enabled        = bool
    instance_types = optional(list(string), ["g6.xlarge"])
    capacity_type  = optional(string, "ON_DEMAND")
    min_size       = optional(number, 0)
    max_size       = optional(number, 1)
    gpus_per_node  = optional(number, 1)
    disk_size_gib  = optional(number, 200)
  })
}
