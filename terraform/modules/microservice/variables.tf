variable "name" {
  description = "Service name (DNS-label style)."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,30}$", var.name))
    error_message = "name must be 2-31 chars: lowercase letters, digits, dashes; start with a letter."
  }
}

variable "name_prefix" {
  description = "<project>-<environment>, prepended to every resource name."
  type        = string
}

variable "is_prod" {
  description = "Turns on deletion protection, longer backups and secret recovery windows."
  type        = bool
}

variable "cluster_name" {
  description = "EKS cluster for the Pod Identity association."
  type        = string
}

variable "namespace" {
  description = "Kubernetes namespace the service runs in."
  type        = string
}

variable "service_account" {
  description = "Kubernetes ServiceAccount name (defaults to the service name)."
  type        = string
  default     = null
}

variable "network" {
  description = "Network context (only used when postgres is enabled)."
  type = object({
    vpc_id                 = string
    private_subnet_ids     = list(string)
    node_security_group_id = string
  })
}

variable "ecr" {
  description = "Create an ECR repository for this service's image."
  type        = bool
  default     = true
}

variable "ecr_keep_images" {
  description = "How many images to keep in ECR."
  type        = number
  default     = 30
}

variable "queue" {
  description = "SQS work queue + DLQ. null = no queue."
  type = object({
    visibility_timeout_seconds = optional(number, 300)
    max_receive_count          = optional(number, 5)
    autoscale                  = optional(bool, false) # let KEDA read this queue's depth
  })
  default = null
}

variable "bucket" {
  description = "Private S3 bucket. null = no bucket."
  type = object({
    versioning                 = optional(bool, true)
    noncurrent_expiration_days = optional(number, 30)
  })
  default = null
}

variable "secrets" {
  description = "Names of Secrets Manager secrets to create (values set out-of-band)."
  type        = list(string)
  default     = []
}

variable "postgres" {
  description = "RDS PostgreSQL instance. null = no database."
  type = object({
    instance_class    = string
    allocated_storage = optional(number, 20)
    multi_az          = optional(bool, false)
    engine_version    = optional(string, "17")
  })
  default = null
}

variable "tags" {
  description = "Extra tags."
  type        = map(string)
  default     = {}
}
