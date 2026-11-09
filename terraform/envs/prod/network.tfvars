vpc_cidr                   = "10.30.0.0/16"
az_count                   = 3
single_nat_gateway         = false # NAT per AZ: an AZ outage doesn't take egress down
enable_interface_endpoints = true
flow_log_retention_days    = 365
