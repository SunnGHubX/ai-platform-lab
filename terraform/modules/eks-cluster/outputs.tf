output "cluster_name" {
  description = "Cluster name."
  value       = module.eks.cluster_name
}

output "cluster_endpoint" {
  description = "API server endpoint."
  value       = module.eks.cluster_endpoint
}

output "cluster_certificate_authority_data" {
  description = "Base64 CA bundle."
  value       = module.eks.cluster_certificate_authority_data
}

output "node_security_group_id" {
  description = "Shared node security group (databases allow ingress from this)."
  value       = module.eks.node_security_group_id
}

output "cluster_primary_security_group_id" {
  description = "EKS-managed cluster security group."
  value       = module.eks.cluster_primary_security_group_id
}
