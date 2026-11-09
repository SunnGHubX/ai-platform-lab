# terraform test - runs offline: the AWS provider is mocked, nothing is created.
mock_provider "aws" {
  # The real data source renders JSON; the mock must too, or IAM resources fail JSON validation.
  mock_data "aws_iam_policy_document" {
    defaults = {
      json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}"
    }
  }

  mock_data "aws_availability_zones" {
    defaults = {
      names = ["us-west-2a", "us-west-2b", "us-west-2c", "us-west-2d"]
    }
  }
}

variables {
  name         = "ai-platform-test"
  region       = "us-west-2"
  cidr         = "10.10.0.0/16"
  cluster_name = "ai-platform-test"
}

run "carves_subnets_deterministically" {
  command = plan

  variables {
    az_count = 3
  }

  assert {
    condition     = output.subnet_cidrs.private == ["10.10.0.0/20", "10.10.16.0/20", "10.10.32.0/20"]
    error_message = "private subnets must be consecutive /20s from the start of the VPC"
  }

  assert {
    condition     = output.subnet_cidrs.public == ["10.10.48.0/24", "10.10.49.0/24", "10.10.50.0/24"]
    error_message = "public subnets must start at 10.x.48.0/24"
  }

  assert {
    condition     = output.subnet_cidrs.intra == ["10.10.52.0/24", "10.10.53.0/24", "10.10.54.0/24"]
    error_message = "intra subnets must start at 10.x.52.0/24"
  }

  assert {
    condition     = length(output.azs) == 3
    error_message = "must use exactly az_count AZs"
  }
}

run "tiers_never_overlap" {
  command = plan

  variables {
    az_count = 3
  }

  # No two subnets may share a network address (cheap overlap check for same-tier sizes)
  assert {
    condition     = length(distinct(concat(output.subnet_cidrs.private, output.subnet_cidrs.public, output.subnet_cidrs.intra))) == 9
    error_message = "subnet CIDRs must be unique"
  }
}

run "dev_skips_paid_interface_endpoints" {
  command = plan

  variables {
    enable_interface_endpoints = false
  }

  assert {
    condition     = length(aws_vpc_endpoint.interface) == 0 && length(aws_security_group.endpoints) == 0
    error_message = "interface endpoints must be off when disabled"
  }

  assert {
    condition     = aws_vpc_endpoint.s3.vpc_endpoint_type == "Gateway"
    error_message = "the free S3 gateway endpoint is always created"
  }
}

run "prod_gets_interface_endpoints" {
  command = plan

  variables {
    enable_interface_endpoints = true
  }

  assert {
    condition     = length(aws_vpc_endpoint.interface) == 6
    error_message = "expected ecr.api, ecr.dkr, sts, logs, ssm, secretsmanager endpoints"
  }
}

run "rejects_non_slash16_cidr" {
  command = plan

  variables {
    cidr = "10.10.0.0/20"
  }

  expect_failures = [var.cidr]
}

run "rejects_single_az" {
  command = plan

  variables {
    az_count = 1
  }

  expect_failures = [var.az_count]
}
