# Partial backend config. The state key is added by the Makefile: <env>/<stack>/terraform.tfstate
bucket       = "ai-platform-tfstate-222222222222-us-west-2"
region       = "us-west-2"
use_lockfile = true # S3-native locking (Terraform >= 1.10) - no DynamoDB table needed
encrypt      = true
