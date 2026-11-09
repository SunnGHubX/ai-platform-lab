variable "project" {
  description = "Project slug; becomes part of the bucket name."
  type        = string
}

variable "noncurrent_version_retention_days" {
  description = "How long to keep old state versions (your undo button)."
  type        = number
  default     = 90
}
