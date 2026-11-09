# One module call = everything a service needs in AWS, with least-privilege IAM generated from
# the features it opts into. The Kubernetes side (Deployment, ServiceAccount) stays in GitOps.

data "aws_caller_identity" "current" {}

locals {
  full_name       = "${var.name_prefix}-${var.name}"
  service_account = coalesce(var.service_account, var.name)

  has_ecr      = var.ecr
  has_queue    = var.queue != null
  has_bucket   = var.bucket != null
  has_postgres = var.postgres != null
  has_secrets  = length(var.secrets) > 0

  has_permissions = local.has_queue || local.has_bucket || local.has_postgres || local.has_secrets
}

# ---------------------------------------------------------------- ECR
resource "aws_ecr_repository" "this" {
  count = local.has_ecr ? 1 : 0

  name                 = "${var.name_prefix}/${var.name}"
  image_tag_mutability = "IMMUTABLE" # a tag always means the same image -> safe GitOps rollbacks
  force_delete         = !var.is_prod

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "KMS"
  }

  tags = var.tags
}

resource "aws_ecr_lifecycle_policy" "this" {
  count = local.has_ecr ? 1 : 0

  repository = aws_ecr_repository.this[0].name
  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged images after 7 days"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 7
        }
        action = { type = "expire" }
      },
      {
        rulePriority = 2
        description  = "Keep the last N images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = var.ecr_keep_images
        }
        action = { type = "expire" }
      },
    ]
  })
}

# ---------------------------------------------------------------- SQS (+ DLQ)
resource "aws_sqs_queue" "dlq" {
  count = local.has_queue ? 1 : 0

  name                      = "${local.full_name}-dlq"
  message_retention_seconds = 1209600 # 14 days to investigate poison messages
  sqs_managed_sse_enabled   = true
  tags                      = var.tags
}

resource "aws_sqs_queue" "this" {
  count = local.has_queue ? 1 : 0

  name                       = local.full_name
  visibility_timeout_seconds = var.queue.visibility_timeout_seconds
  sqs_managed_sse_enabled    = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq[0].arn
    maxReceiveCount     = var.queue.max_receive_count
  })

  tags = var.tags
}

resource "aws_sqs_queue_redrive_allow_policy" "dlq" {
  count = local.has_queue ? 1 : 0

  queue_url = aws_sqs_queue.dlq[0].id
  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = [aws_sqs_queue.this[0].arn]
  })
}

# ---------------------------------------------------------------- S3
resource "aws_s3_bucket" "this" {
  count = local.has_bucket ? 1 : 0

  # Globally unique and self-describing; account ID avoids collisions across envs/accounts.
  bucket        = "${local.full_name}-${data.aws_caller_identity.current.account_id}"
  force_destroy = !var.is_prod
  tags          = var.tags
}

resource "aws_s3_bucket_versioning" "this" {
  count = local.has_bucket ? 1 : 0

  bucket = aws_s3_bucket.this[0].id
  versioning_configuration {
    status = var.bucket.versioning ? "Enabled" : "Suspended"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  count = local.has_bucket ? 1 : 0

  bucket = aws_s3_bucket.this[0].id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "this" {
  count = local.has_bucket ? 1 : 0

  bucket                  = aws_s3_bucket.this[0].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "this" {
  count = local.has_bucket ? 1 : 0

  bucket = aws_s3_bucket.this[0].id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "this" {
  count = local.has_bucket ? 1 : 0

  bucket = aws_s3_bucket.this[0].id
  rule {
    id     = "expire-noncurrent"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration {
      noncurrent_days = var.bucket.noncurrent_expiration_days
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

data "aws_iam_policy_document" "bucket_tls_only" {
  count = local.has_bucket ? 1 : 0

  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.this[0].arn,
      "${aws_s3_bucket.this[0].arn}/*",
    ]
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "this" {
  count = local.has_bucket ? 1 : 0

  bucket = aws_s3_bucket.this[0].id
  policy = data.aws_iam_policy_document.bucket_tls_only[0].json
}

# ---------------------------------------------------------------- Secrets Manager
# Terraform creates the secret *container* only. Values are set out-of-band
# (console/CLI/CI) so they never land in Terraform state.
resource "aws_secretsmanager_secret" "this" {
  for_each = toset(var.secrets)

  name                    = "${var.name_prefix}/${var.name}/${each.key}"
  recovery_window_in_days = var.is_prod ? 30 : 0
  tags                    = var.tags
}

# ---------------------------------------------------------------- PostgreSQL (RDS)
resource "aws_db_subnet_group" "this" {
  count = local.has_postgres ? 1 : 0

  name       = local.full_name
  subnet_ids = var.network.private_subnet_ids
  tags       = var.tags
}

resource "aws_security_group" "db" {
  count = local.has_postgres ? 1 : 0

  name_prefix = "${local.full_name}-db-"
  description = "PostgreSQL for ${var.name}"
  vpc_id      = var.network.vpc_id
  tags        = var.tags

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_vpc_security_group_ingress_rule" "db_from_nodes" {
  count = local.has_postgres ? 1 : 0

  security_group_id            = aws_security_group.db[0].id
  description                  = "PostgreSQL from EKS nodes"
  referenced_security_group_id = var.network.node_security_group_id
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
}

resource "aws_db_instance" "this" {
  count = local.has_postgres ? 1 : 0

  identifier     = local.full_name
  engine         = "postgres"
  engine_version = var.postgres.engine_version
  instance_class = var.postgres.instance_class

  allocated_storage     = var.postgres.allocated_storage
  max_allocated_storage = var.postgres.allocated_storage * 4 # storage autoscaling headroom
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = replace(var.name, "-", "_")
  username = "app"
  # RDS generates + rotates the password in Secrets Manager; it is never in Terraform state.
  manage_master_user_password         = true
  iam_database_authentication_enabled = true

  multi_az               = var.postgres.multi_az
  db_subnet_group_name   = aws_db_subnet_group.this[0].name
  vpc_security_group_ids = [aws_security_group.db[0].id]
  publicly_accessible    = false

  backup_retention_period   = var.is_prod ? 14 : 1
  deletion_protection       = var.is_prod
  skip_final_snapshot       = !var.is_prod
  final_snapshot_identifier = var.is_prod ? "${local.full_name}-final" : null
  copy_tags_to_snapshot     = true

  auto_minor_version_upgrade  = true
  allow_major_version_upgrade = false
  apply_immediately           = !var.is_prod # prod changes wait for the maintenance window

  tags = var.tags
}

# ---------------------------------------------------------------- IAM via EKS Pod Identity
data "aws_iam_policy_document" "trust" {
  statement {
    actions = ["sts:AssumeRole", "sts:TagSession"]
    principals {
      type        = "Service"
      identifiers = ["pods.eks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "this" {
  name               = local.full_name
  assume_role_policy = data.aws_iam_policy_document.trust.json
  tags               = var.tags
}

# Policy is generated from the features this service enabled - nothing more.
data "aws_iam_policy_document" "permissions" {
  count = local.has_permissions ? 1 : 0

  dynamic "statement" {
    for_each = local.has_queue ? [1] : []
    content {
      sid = "QueueConsume"
      actions = [
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:SendMessage",
        "sqs:ChangeMessageVisibility",
        "sqs:GetQueueAttributes",
        "sqs:GetQueueUrl",
      ]
      resources = [aws_sqs_queue.this[0].arn]
    }
  }

  dynamic "statement" {
    for_each = local.has_bucket ? [1] : []
    content {
      sid       = "BucketList"
      actions   = ["s3:ListBucket"]
      resources = [aws_s3_bucket.this[0].arn]
    }
  }

  dynamic "statement" {
    for_each = local.has_bucket ? [1] : []
    content {
      sid       = "BucketObjects"
      actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
      resources = ["${aws_s3_bucket.this[0].arn}/*"]
    }
  }

  dynamic "statement" {
    for_each = local.has_secrets || local.has_postgres ? [1] : []
    content {
      sid     = "ReadOwnSecrets"
      actions = ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"]
      resources = concat(
        [for s in aws_secretsmanager_secret.this : s.arn],
        local.has_postgres ? [aws_db_instance.this[0].master_user_secret[0].secret_arn] : [],
      )
    }
  }
}

resource "aws_iam_role_policy" "this" {
  count = local.has_permissions ? 1 : 0

  name   = "service-permissions"
  role   = aws_iam_role.this.id
  policy = data.aws_iam_policy_document.permissions[0].json
}

resource "aws_eks_pod_identity_association" "this" {
  cluster_name    = var.cluster_name
  namespace       = var.namespace
  service_account = local.service_account
  role_arn        = aws_iam_role.this.arn
  tags            = var.tags
}
