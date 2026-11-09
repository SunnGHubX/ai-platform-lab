locals {
  stack        = "network"
  cluster_name = local.name_prefix # naming convention shared with the eks stack
}

module "network" {
  source = "../../modules/network"

  name         = local.name_prefix
  region       = var.region
  cidr         = var.vpc_cidr
  az_count     = var.az_count
  cluster_name = local.cluster_name

  single_nat_gateway         = var.single_nat_gateway
  enable_interface_endpoints = var.enable_interface_endpoints
  flow_log_retention_days    = var.flow_log_retention_days
}

# ---- Publish the contract downstream stacks consume (see README: "Cross-stack contracts") ----
resource "aws_ssm_parameter" "vpc_id" {
  name  = "${local.ssm_prefix}/network/vpc_id"
  type  = "String"
  value = module.network.vpc_id
}

resource "aws_ssm_parameter" "vpc_cidr" {
  name  = "${local.ssm_prefix}/network/vpc_cidr"
  type  = "String"
  value = module.network.vpc_cidr
}

resource "aws_ssm_parameter" "private_subnet_ids" {
  name  = "${local.ssm_prefix}/network/private_subnet_ids"
  type  = "StringList"
  value = join(",", module.network.private_subnet_ids)
}

resource "aws_ssm_parameter" "intra_subnet_ids" {
  name  = "${local.ssm_prefix}/network/intra_subnet_ids"
  type  = "StringList"
  value = join(",", module.network.intra_subnet_ids)
}
