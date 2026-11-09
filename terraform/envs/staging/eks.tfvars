kubernetes_version = "1.34"

endpoint_public_access       = true
endpoint_public_access_cidrs = ["203.0.113.0/24"] # <- office/VPN egress

admin_role_arns = [
  "arn:aws:iam::222222222222:role/ai-platform-staging-tf-apply",
]

system_node_group = {
  instance_types = ["m6a.large"]
  min_size       = 2
  max_size       = 3
}

cpu_node_group = {
  instance_types = ["m6a.xlarge", "m7a.xlarge"]
  capacity_type  = "ON_DEMAND"
  min_size       = 1
  max_size       = 6
}

gpu_node_group = {
  enabled        = true
  instance_types = ["g6.xlarge"]
  capacity_type  = "ON_DEMAND"
  min_size       = 0
  max_size       = 2
}
