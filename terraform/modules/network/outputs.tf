output "vpc_id" {
  description = "VPC ID."
  value       = module.vpc.vpc_id
}

output "vpc_cidr" {
  description = "VPC CIDR."
  value       = module.vpc.vpc_cidr_block
}

output "private_subnet_ids" {
  description = "Private subnets (nodes, pods, databases)."
  value       = module.vpc.private_subnets
}

output "public_subnet_ids" {
  description = "Public subnets (internet-facing load balancers)."
  value       = module.vpc.public_subnets
}

output "intra_subnet_ids" {
  description = "Intra subnets (EKS control plane ENIs)."
  value       = module.vpc.intra_subnets
}

output "azs" {
  description = "AZs in use."
  value       = local.azs
}

output "subnet_cidrs" {
  description = "Computed subnet CIDRs per tier (exposed so the carving logic is unit-testable)."
  value = {
    private = local.private_subnets
    public  = local.public_subnets
    intra   = local.intra_subnets
  }
}
