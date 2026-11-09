# Symlinked into every stack.
provider "aws" {
  region = var.region

  # Guardrail: a prod tfvars file can never be applied with dev credentials (or vice versa).
  allowed_account_ids = [var.account_id]

  dynamic "assume_role" {
    for_each = var.assume_role_arn == null ? [] : [var.assume_role_arn]
    content {
      role_arn     = assume_role.value
      session_name = "terraform-${var.environment}-${local.stack}"
    }
  }

  default_tags {
    tags = local.default_tags
  }
}
