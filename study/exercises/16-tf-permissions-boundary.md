# 16 · Permissions boundaries + replace the admin CI role ★★★

**Track:** Security · least privilege · **Complex**

**Scenario:** The bootstrap stack gives the CI apply role `AdministratorAccess` (checkov flags it, and `SECURITY.md` admits it). A compromised workflow could create an IAM user with admin and walk away. Also, every service role in the catalog could, in theory, be edited to grant itself more.

## Requirements

1. New module `terraform/modules/permissions-boundary/` that outputs `policy_arn` for a boundary that:
   - denies `iam:*User*`, `iam:CreateAccessKey`, `organizations:*`, `account:*`
   - denies any IAM role creation/update **unless** the new role also carries this same boundary (`iam:PermissionsBoundary` condition): this stops privilege escalation
   - denies actions outside `var.allowed_regions` (exempting global services: IAM, STS, CloudFront, Route 53, support)
   - denies `kms:Decrypt` unless the key has tag `project = <project>` (`aws:ResourceTag`)
2. Every `aws_iam_role` created by `modules/microservice`, `modules/eks-cluster` and the `services` stack sets `permissions_boundary`.
3. Bootstrap: the apply role **drops `AdministratorAccess`**. Replace it with a scoped policy (services this repo actually uses: ec2/vpc, eks, iam (bounded), s3, kms, sqs, rds, secretsmanager, ssm, ecr, logs, elasticache, autoscaling) **plus** the boundary.

## Tasks

1. Tests first: a test asserting the boundary JSON contains the escalation-prevention statement; and a test in `stacks/services` asserting every role has `permissions_boundary != null`. (Hint: `alltrue([for r in ... : r.permissions_boundary != null])`.)
2. Implement and wire through as a variable (`permissions_boundary_arn`) published by bootstrap to SSM.
3. Update `SECURITY.md`: remove the "Scope note" caveat.

## Acceptance

- [ ] No `AdministratorAccess` in `terraform/`
- [ ] Every role resource in modules sets `permissions_boundary`
- [ ] Terraform tests pass

**Interview angle:** IAM privilege escalation paths (iam:PassRole, CreatePolicyVersion, UpdateAssumeRolePolicy), boundaries vs SCPs vs session policies, how to safely delegate IAM to app teams.

## Validate

```bash
git checkout -b ex/16-<short-name>
make exercise EX=16          # local: ✅/❌ per acceptance check
git push -u origin HEAD       # CI: the `exercise` workflow runs the same checks (strict) + every other pipeline
```
