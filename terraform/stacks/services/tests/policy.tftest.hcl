# Policy-as-code at the Terraform layer: environment rules enforced by variable validation.
mock_provider "aws" {
  override_during = plan

  mock_data "aws_ssm_parameter" {
    defaults = {
      value = "mock-value"
    }
  }
}

variables {
  environment = "prod"
  region      = "us-west-2"
  account_id  = "333333333333"
  owner       = "platform-team"
  cost_center = "test"
}

run "prod_rejects_single_az_database" {
  command = plan

  variables {
    services = {
      mlflow = {
        namespace = "mlops"
        postgres  = { instance_class = "db.r7g.large", multi_az = false }
      }
    }
  }

  expect_failures = [var.services]
}

run "prod_rejects_unversioned_bucket" {
  command = plan

  variables {
    services = {
      batch-embedder = {
        namespace = "inference"
        bucket    = { versioning = false }
      }
    }
  }

  expect_failures = [var.services]
}

run "prod_accepts_compliant_catalog" {
  command = plan

  variables {
    services = {
      mlflow = {
        namespace = "mlops"
        bucket    = {}
        postgres  = { instance_class = "db.r7g.large", multi_az = true }
      }
      batch-embedder = {
        namespace = "inference"
        queue     = { autoscale = true }
      }
    }
  }

  assert {
    condition     = length(aws_iam_role.keda_operator) == 1
    error_message = "a queue with autoscale = true must create the KEDA operator role"
  }
}

run "no_keda_role_without_queue_autoscaling" {
  command = plan

  variables {
    environment = "dev"
    account_id  = "111111111111"
    services = {
      inference-gateway = { namespace = "inference" }
    }
  }

  assert {
    condition     = length(aws_iam_role.keda_operator) == 0
    error_message = "KEDA role must not exist when nothing scales on a queue"
  }
}
