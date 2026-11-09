kubernetes_version = "1.34"

endpoint_public_access       = true
endpoint_public_access_cidrs = ["203.0.113.10/32"] # <- your home/office IP

system_node_group = {
  instance_types = ["t3a.large"]
  min_size       = 2
  max_size       = 3
}

cpu_node_group = {
  instance_types = ["m6a.large", "m7a.large", "m6i.large"] # diversified for Spot capacity
  capacity_type  = "SPOT"
  min_size       = 0
  max_size       = 4
}

gpu_node_group = {
  enabled        = true
  instance_types = ["g6.xlarge", "g5.xlarge"] # 1x L4 / 1x A10G
  capacity_type  = "SPOT"
  min_size       = 0 # scale from zero: pay only while vLLM is running
  max_size       = 1
}
