# Symlinked into every stack. One place to bump Terraform / provider constraints.
terraform {
  required_version = ">= 1.10.0" # S3 native state locking (use_lockfile)

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # Partial config: bucket/region come from envs/<env>/backend.hcl, key is set by the Makefile
  # as <env>/<stack>/terraform.tfstate -> one state file per (environment, stack).
  backend "s3" {}
}
