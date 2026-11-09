variable "services" {
  description = "Service catalog: key = service name, value = which AWS features it needs."
  type = map(object({
    namespace       = string
    service_account = optional(string)
    ecr             = optional(bool, true)
    queue = optional(object({
      visibility_timeout_seconds = optional(number, 300)
      max_receive_count          = optional(number, 5)
      autoscale                  = optional(bool, false)
    }))
    bucket = optional(object({
      versioning                 = optional(bool, true)
      noncurrent_expiration_days = optional(number, 30)
    }))
    secrets = optional(list(string), [])
    postgres = optional(object({
      instance_class    = string
      allocated_storage = optional(number, 20)
      multi_az          = optional(bool, false)
      engine_version    = optional(string, "17")
    }))
  }))

  # Environment policy enforced at plan time (cross-variable validation, Terraform >= 1.9).
  validation {
    condition = var.environment != "prod" || alltrue([
      for s in values(var.services) : s.postgres == null || try(s.postgres.multi_az, false)
    ])
    error_message = "In prod every postgres database must set multi_az = true."
  }

  validation {
    condition = var.environment != "prod" || alltrue([
      for s in values(var.services) : s.bucket == null || try(s.bucket.versioning, true)
    ])
    error_message = "In prod every bucket must keep versioning enabled."
  }
}
