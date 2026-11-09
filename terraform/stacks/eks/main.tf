locals {
  stack        = "eks"
  cluster_name = local.name_prefix
}

# ---- Inputs from the network stack (contract, not remote state) ----
data "aws_ssm_parameter" "vpc_id" {
  name = "${local.ssm_prefix}/network/vpc_id"
}

data "aws_ssm_parameter" "private_subnet_ids" {
  name = "${local.ssm_prefix}/network/private_subnet_ids"
}

data "aws_ssm_parameter" "intra_subnet_ids" {
  name = "${local.ssm_prefix}/network/intra_subnet_ids"
}

module "eks" {
  source = "../../modules/eks-cluster"

  name               = local.cluster_name
  kubernetes_version = var.kubernetes_version

  vpc_id             = data.aws_ssm_parameter.vpc_id.value
  private_subnet_ids = split(",", data.aws_ssm_parameter.private_subnet_ids.value)
  intra_subnet_ids   = split(",", data.aws_ssm_parameter.intra_subnet_ids.value)

  endpoint_public_access       = var.endpoint_public_access
  endpoint_public_access_cidrs = var.endpoint_public_access_cidrs
  enable_creator_admin         = var.environment != "prod" # prod admins come only from admin_role_arns
  admin_role_arns              = var.admin_role_arns

  system_node_group = var.system_node_group
  cpu_node_group    = var.cpu_node_group
  gpu_node_group    = var.gpu_node_group
}

# ---- Publish for the services stack ----
resource "aws_ssm_parameter" "cluster_name" {
  name  = "${local.ssm_prefix}/eks/cluster_name"
  type  = "String"
  value = module.eks.cluster_name
}

resource "aws_ssm_parameter" "node_security_group_id" {
  name  = "${local.ssm_prefix}/eks/node_security_group_id"
  type  = "String"
  value = module.eks.node_security_group_id
}
