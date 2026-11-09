vpc_cidr                   = "10.10.0.0/16"
az_count                   = 2     # minimum EKS allows
single_nat_gateway         = true  # ~$32/mo instead of ~$96
enable_interface_endpoints = false # save ~$80/mo; S3 gateway endpoint is still on
flow_log_retention_days    = 7
