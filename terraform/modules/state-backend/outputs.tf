output "bucket_name" {
  description = "State bucket name for envs/<env>/backend.hcl."
  value       = aws_s3_bucket.state.bucket
}

output "bucket_arn" {
  description = "State bucket ARN (for CI role policies)."
  value       = aws_s3_bucket.state.arn
}

output "kms_key_arn" {
  description = "KMS key that encrypts state."
  value       = aws_kms_key.state.arn
}
