variable "project" {
  description = "Project slug; becomes part of the bucket name."
  type        = string
}

variable "noncurrent_version_retention_days" {
  description = "How long to keep old state versions (your undo button)."
  type        = number
  default     = 90
}

variable "enforce_tls_policy" {
  description = "Deny non-TLS access to the state bucket. Only disabled for emulator tests (moto ignores policy conditions)."
  type        = bool
  default     = true
}
