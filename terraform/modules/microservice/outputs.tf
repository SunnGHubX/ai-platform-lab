output "role_arn" {
  description = "IAM role the service's pods assume via Pod Identity."
  value       = aws_iam_role.this.arn
}

output "service_account" {
  description = "ServiceAccount the GitOps manifests must use."
  value       = local.service_account
}

output "ecr_repository_url" {
  description = "ECR repository URL."
  value       = try(aws_ecr_repository.this[0].repository_url, null)
}

output "queue_url" {
  description = "SQS queue URL."
  value       = try(aws_sqs_queue.this[0].url, null)
}

output "queue_arn" {
  description = "SQS queue ARN."
  value       = try(aws_sqs_queue.this[0].arn, null)
}

output "queue_name" {
  description = "SQS queue name (KEDA aws-sqs-queue scaler uses the URL or name)."
  value       = try(aws_sqs_queue.this[0].name, null)
}

output "bucket_name" {
  description = "S3 bucket name."
  value       = try(aws_s3_bucket.this[0].bucket, null)
}

output "secret_arns" {
  description = "Secrets Manager ARNs by short name."
  value       = { for k, s in aws_secretsmanager_secret.this : k => s.arn }
}

output "db_endpoint" {
  description = "PostgreSQL endpoint (host:port)."
  value       = try(aws_db_instance.this[0].endpoint, null)
}

output "db_master_secret_arn" {
  description = "Secrets Manager ARN holding the RDS-managed master password."
  value       = try(aws_db_instance.this[0].master_user_secret[0].secret_arn, null)
}
