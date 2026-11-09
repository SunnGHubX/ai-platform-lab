locals {
  gpu_enabled = var.gpu_node_group.enabled

  base_node_groups = {
    # Critical add-ons (CoreDNS, Argo CD, KEDA, Prometheus) - always on-demand, never scaled to zero.
    system = {
      ami_type       = "AL2023_x86_64_STANDARD"
      instance_types = var.system_node_group.instance_types
      capacity_type  = "ON_DEMAND"
      min_size       = var.system_node_group.min_size
      max_size       = var.system_node_group.max_size
      desired_size   = var.system_node_group.min_size
      labels         = { "node-role" = "system" }
    }

    # General CPU workloads (MLflow, gateways, batch). Spot in dev, on-demand in prod.
    cpu = {
      ami_type       = "AL2023_x86_64_STANDARD"
      instance_types = var.cpu_node_group.instance_types
      capacity_type  = var.cpu_node_group.capacity_type
      min_size       = var.cpu_node_group.min_size
      max_size       = var.cpu_node_group.max_size
      desired_size   = var.cpu_node_group.min_size
      labels         = { "workload" = "general" }
    }
  }

  # GPU pool: tainted so only pods that tolerate nvidia.com/gpu land here (matches platform/vllm).
  gpu_node_group = local.gpu_enabled ? {
    gpu = {
      ami_type       = "AL2023_x86_64_NVIDIA" # NVIDIA driver + container toolkit baked in
      instance_types = var.gpu_node_group.instance_types
      capacity_type  = var.gpu_node_group.capacity_type
      min_size       = var.gpu_node_group.min_size
      max_size       = var.gpu_node_group.max_size
      desired_size   = var.gpu_node_group.min_size
      labels = {
        "workload"               = "gpu"
        "nvidia.com/gpu.present" = "true"
      }
      taints = {
        gpu = {
          key    = "nvidia.com/gpu"
          value  = "true"
          effect = "NO_SCHEDULE"
        }
      }
      block_device_mappings = {
        xvda = {
          device_name = "/dev/xvda"
          ebs = {
            volume_size           = var.gpu_node_group.disk_size_gib # container images + model weights are huge
            volume_type           = "gp3"
            encrypted             = true
            delete_on_termination = true
          }
        }
      }
    }
  } : {}

  # Scale-from-zero: when the GPU group has 0 nodes, Cluster Autoscaler can only learn what a
  # node *would* look like from ASG tags. Managed node groups do NOT copy tags to the ASG,
  # so we tag the ASG explicitly below.
  gpu_asg_tags = local.gpu_enabled ? {
    "k8s.io/cluster-autoscaler/enabled"                                = "true"
    "k8s.io/cluster-autoscaler/${var.name}"                            = "owned"
    "k8s.io/cluster-autoscaler/node-template/label/workload"           = "gpu"
    "k8s.io/cluster-autoscaler/node-template/taint/nvidia.com/gpu"     = "true:NoSchedule"
    "k8s.io/cluster-autoscaler/node-template/resources/nvidia.com/gpu" = tostring(var.gpu_node_group.gpus_per_node)
  } : {}

  access_entries = {
    for i, arn in var.admin_role_arns : "admin-${i}" => {
      principal_arn = arn
      policy_associations = {
        admin = {
          policy_arn   = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
          access_scope = { type = "cluster" }
        }
      }
    }
  }
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 21.29"

  name               = var.name
  kubernetes_version = var.kubernetes_version

  vpc_id                   = var.vpc_id
  subnet_ids               = var.private_subnet_ids
  control_plane_subnet_ids = var.intra_subnet_ids

  endpoint_private_access      = true
  endpoint_public_access       = var.endpoint_public_access
  endpoint_public_access_cidrs = var.endpoint_public_access_cidrs

  enable_cluster_creator_admin_permissions = var.enable_creator_admin
  access_entries                           = local.access_entries

  enabled_log_types = ["api", "audit", "authenticator"]

  addons = {
    vpc-cni = {
      before_compute = true # must exist before nodes join or pods get no IPs
    }
    eks-pod-identity-agent = {
      before_compute = true # every workload role in this repo uses Pod Identity, not IRSA
    }
    kube-proxy         = {}
    coredns            = {}
    aws-ebs-csi-driver = {}
  }

  eks_managed_node_groups = merge(local.base_node_groups, local.gpu_node_group)

  node_security_group_tags = {
    "karpenter.sh/discovery" = var.name
  }

  tags = var.tags
}

resource "aws_autoscaling_group_tag" "gpu" {
  for_each = local.gpu_asg_tags

  autoscaling_group_name = one(module.eks.eks_managed_node_groups["gpu"].node_group_autoscaling_group_names)

  tag {
    key                 = each.key
    value               = each.value
    propagate_at_launch = false
  }
}

# ---- EBS CSI driver identity (Pod Identity) ----
data "aws_iam_policy_document" "pod_identity_trust" {
  statement {
    actions = ["sts:AssumeRole", "sts:TagSession"]
    principals {
      type        = "Service"
      identifiers = ["pods.eks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ebs_csi" {
  name               = "${var.name}-ebs-csi"
  assume_role_policy = data.aws_iam_policy_document.pod_identity_trust.json
  tags               = var.tags
}

resource "aws_iam_role_policy_attachment" "ebs_csi" {
  role       = aws_iam_role.ebs_csi.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy"
}

resource "aws_eks_pod_identity_association" "ebs_csi" {
  cluster_name    = module.eks.cluster_name
  namespace       = "kube-system"
  service_account = "ebs-csi-controller-sa"
  role_arn        = aws_iam_role.ebs_csi.arn
}
