output "state_bucket" {
  description = "Put this in envs/<env>/backend.hcl."
  value       = module.state_backend.bucket_name
}

output "plan_role_arn" {
  description = "Set as GitHub variable AWS_PLAN_ROLE_ARN_<ENV>."
  value       = aws_iam_role.plan.arn
}

output "apply_role_arn" {
  description = "Set as GitHub variable AWS_APPLY_ROLE_ARN_<ENV>."
  value       = aws_iam_role.apply.arn
}
