kubernetes_version = "1.34"

endpoint_public_access = false # API reachable only from inside the VPC / via VPN

admin_role_arns = [
  "arn:aws:iam::333333333333:role/ai-platform-prod-tf-apply",
  # "arn:aws:iam::333333333333:role/aws-reserved/sso.amazonaws.com/AWSReservedSSO_AdministratorAccess_xxxx",
]

system_node_group = {
  instance_types = ["m6a.xlarge"]
  min_size       = 3 # one per AZ
  max_size       = 6
}

cpu_node_group = {
  instance_types = ["m6a.2xlarge", "m7a.2xlarge"]
  capacity_type  = "ON_DEMAND"
  min_size       = 3
  max_size       = 20
}

gpu_node_group = {
  enabled        = true
  instance_types = ["g6e.xlarge"] # 1x L40S, 48 GB - fits 7-8B models at full precision
  capacity_type  = "ON_DEMAND"
  min_size       = 1 # keep one warm: no cold start for the first request
  max_size       = 8
  disk_size_gib  = 500
}
