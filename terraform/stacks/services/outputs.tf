output "services" {
  description = "Per-service AWS wiring for the GitOps manifests."
  value = {
    for k, s in module.service : k => {
      role_arn           = s.role_arn
      service_account    = s.service_account
      ecr_repository_url = s.ecr_repository_url
      queue_url          = s.queue_url
      bucket_name        = s.bucket_name
      db_endpoint        = s.db_endpoint
    }
  }
}

output "keda_operator_role_arn" {
  description = "Role KEDA uses for the aws-sqs-queue scaler (null if no service autoscales on a queue)."
  value       = try(aws_iam_role.keda_operator[0].arn, null)
}
