# terraform test - the AWS provider is mocked, so these run in CI with no credentials.
# They pin the module's *contract*: which resources exist and what IAM a service gets.
mock_provider "aws" {
  # The real data source renders JSON; the mock must too, or IAM resources fail JSON validation.
  mock_data "aws_iam_policy_document" {
    defaults = {
      json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}"
    }
  }

  mock_data "aws_caller_identity" {
    defaults = {
      account_id = "123456789012"
    }
  }
}

variables {
  name_prefix  = "ai-platform-dev"
  is_prod      = false
  cluster_name = "ai-platform-dev"
  namespace    = "inference"
  network = {
    vpc_id                 = "vpc-0123456789abcdef0"
    private_subnet_ids     = ["subnet-a", "subnet-b"]
    node_security_group_id = "sg-0123456789abcdef0"
  }
}

run "image_only_service_gets_no_permissions" {
  variables {
    name = "inference-gateway"
  }

  assert {
    condition     = length(aws_ecr_repository.this) == 1 && aws_ecr_repository.this[0].image_tag_mutability == "IMMUTABLE"
    error_message = "every service image repo must be immutable"
  }

  assert {
    condition     = length(aws_iam_role_policy.this) == 0
    error_message = "a service with no AWS features must not get an inline policy"
  }

  assert {
    condition     = aws_eks_pod_identity_association.this.service_account == "inference-gateway"
    error_message = "service account defaults to the service name"
  }
}

run "queue_service_gets_only_queue_permissions" {
  variables {
    name  = "batch-embedder"
    queue = { max_receive_count = 3 }
  }

  assert {
    condition     = length(aws_sqs_queue.this) == 1 && length(aws_sqs_queue.dlq) == 1
    error_message = "queue + DLQ expected"
  }

  assert {
    condition     = jsondecode(aws_sqs_queue.this[0].redrive_policy).maxReceiveCount == 3
    error_message = "redrive policy must carry max_receive_count"
  }

  assert {
    condition     = join(",", [for s in data.aws_iam_policy_document.permissions[0].statement : s.sid]) == "QueueConsume"
    error_message = "least privilege: only the QueueConsume statement may be generated"
  }

  assert {
    condition     = length(aws_s3_bucket.this) == 0 && length(aws_db_instance.this) == 0
    error_message = "no bucket or database unless asked for"
  }
}

run "dev_resources_are_disposable" {
  variables {
    name    = "scratch"
    bucket  = {}
    secrets = ["token"]
  }

  assert {
    condition     = aws_s3_bucket.this[0].force_destroy == true
    error_message = "dev buckets can be force-destroyed"
  }

  assert {
    condition     = aws_secretsmanager_secret.this["token"].recovery_window_in_days == 0
    error_message = "dev secrets delete immediately"
  }

  assert {
    condition     = aws_s3_bucket.this[0].bucket == "ai-platform-dev-scratch-123456789012"
    error_message = "bucket naming convention: <prefix>-<service>-<account>"
  }
}

run "prod_full_service_is_protected" {
  variables {
    name        = "mlflow"
    name_prefix = "ai-platform-prod"
    is_prod     = true
    ecr         = false
    bucket      = {}
    secrets     = ["oauth-client"]
    postgres    = { instance_class = "db.r7g.large", multi_az = true }
  }

  override_resource {
    target = aws_db_instance.this
    values = {
      master_user_secret = [{
        kms_key_id    = "arn:aws:kms:us-west-2:123456789012:key/test"
        secret_arn    = "arn:aws:secretsmanager:us-west-2:123456789012:secret:rds-master"
        secret_status = "active"
      }]
    }
  }

  assert {
    condition     = aws_db_instance.this[0].deletion_protection && aws_db_instance.this[0].backup_retention_period == 14
    error_message = "prod databases need deletion protection and 14-day backups"
  }

  assert {
    condition     = aws_db_instance.this[0].manage_master_user_password && aws_db_instance.this[0].publicly_accessible == false
    error_message = "password must be RDS-managed and the DB private"
  }

  assert {
    condition     = aws_s3_bucket.this[0].force_destroy == false
    error_message = "prod buckets must not be force-destroyable"
  }

  assert {
    condition     = length(aws_ecr_repository.this) == 0
    error_message = "ecr = false must skip the repository"
  }

  assert {
    condition     = join(",", sort([for s in data.aws_iam_policy_document.permissions[0].statement : s.sid])) == "BucketList,BucketObjects,ReadOwnSecrets"
    error_message = "IAM must cover exactly bucket + secrets (incl. RDS master secret)"
  }
}

run "rejects_bad_service_names" {
  command = plan

  variables {
    name = "Bad_Name"
  }

  expect_failures = [var.name]
}
