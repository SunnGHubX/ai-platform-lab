locals {
  stack = "services"

  keda_needs_sqs = anytrue([for s in values(var.services) : try(s.queue.autoscale, false)])
}

# ---- Inputs from network + eks stacks ----
data "aws_ssm_parameter" "vpc_id" {
  name = "${local.ssm_prefix}/network/vpc_id"
}

data "aws_ssm_parameter" "private_subnet_ids" {
  name = "${local.ssm_prefix}/network/private_subnet_ids"
}

data "aws_ssm_parameter" "cluster_name" {
  name = "${local.ssm_prefix}/eks/cluster_name"
}

data "aws_ssm_parameter" "node_security_group_id" {
  name = "${local.ssm_prefix}/eks/node_security_group_id"
}

# ---- The service catalog: one module instance per entry in envs/<env>/services.tfvars ----
module "service" {
  source   = "../../modules/microservice"
  for_each = var.services

  name            = each.key
  name_prefix     = local.name_prefix
  is_prod         = var.environment == "prod"
  cluster_name    = data.aws_ssm_parameter.cluster_name.value
  namespace       = each.value.namespace
  service_account = each.value.service_account

  network = {
    vpc_id                 = data.aws_ssm_parameter.vpc_id.value
    private_subnet_ids     = split(",", data.aws_ssm_parameter.private_subnet_ids.value)
    node_security_group_id = data.aws_ssm_parameter.node_security_group_id.value
  }

  ecr      = each.value.ecr
  queue    = each.value.queue
  bucket   = each.value.bucket
  secrets  = each.value.secrets
  postgres = each.value.postgres

  tags = { Service = each.key }
}

# ---- KEDA operator: read queue depth ONLY for services that opted into queue autoscaling ----
data "aws_iam_policy_document" "pod_identity_trust" {
  statement {
    actions = ["sts:AssumeRole", "sts:TagSession"]
    principals {
      type        = "Service"
      identifiers = ["pods.eks.amazonaws.com"]
    }
  }
}

data "aws_iam_policy_document" "keda_sqs" {
  count = local.keda_needs_sqs ? 1 : 0

  statement {
    sid       = "ReadQueueDepth"
    actions   = ["sqs:GetQueueAttributes"]
    resources = [for k, s in module.service : s.queue_arn if try(var.services[k].queue.autoscale, false)]
  }
}

resource "aws_iam_role" "keda_operator" {
  count = local.keda_needs_sqs ? 1 : 0

  name               = "${local.name_prefix}-keda-operator"
  assume_role_policy = data.aws_iam_policy_document.pod_identity_trust.json
}

resource "aws_iam_role_policy" "keda_operator" {
  count = local.keda_needs_sqs ? 1 : 0

  name   = "read-queue-depth"
  role   = aws_iam_role.keda_operator[0].id
  policy = data.aws_iam_policy_document.keda_sqs[0].json
}

resource "aws_eks_pod_identity_association" "keda_operator" {
  count = local.keda_needs_sqs ? 1 : 0

  cluster_name    = data.aws_ssm_parameter.cluster_name.value
  namespace       = "keda"
  service_account = "keda-operator"
  role_arn        = aws_iam_role.keda_operator[0].arn
}

# ---- Hand-off to GitOps: one JSON config per service (External Secrets / Helm can read it) ----
resource "aws_ssm_parameter" "service_config" {
  for_each = module.service

  name = "${local.ssm_prefix}/services/${each.key}/config"
  type = "String"
  value = jsonencode({
    role_arn           = each.value.role_arn
    service_account    = each.value.service_account
    ecr_repository_url = each.value.ecr_repository_url
    queue_url          = each.value.queue_url
    bucket_name        = each.value.bucket_name
    db_endpoint        = each.value.db_endpoint
    secret_arns        = each.value.secret_arns
  })
}
