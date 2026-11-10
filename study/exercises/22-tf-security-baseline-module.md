# 22 · Custom module: `security-baseline` for every AWS account ★★★

**Track:** Security · Terraform modules · detective controls · **Complex**

**Scenario:** New accounts (dev/staging/prod) are created by the bootstrap stack, but nothing turns on CloudTrail, GuardDuty or default encryption. An incident in an account with no audit trail can't be investigated.

## Requirements

`terraform/modules/security-baseline/`, called from `envs/_global/bootstrap`:

| Control | Resource(s) | Detail |
|---|---|---|
| Audit trail | `aws_cloudtrail` | multi-region, **log file validation**, KMS-encrypted (exercise 14 module), to a `secure-bucket` (exercise 15) |
| Threat detection | `aws_guardduty_detector` | enabled; S3 + EKS protection features |
| Posture | `aws_securityhub_account` + standards subscription | AWS Foundational Security Best Practices |
| Config | `aws_config_configuration_recorder` + delivery channel | all resources |
| External access | `aws_accessanalyzer_analyzer` | account analyzer |
| Defaults | `aws_ebs_encryption_by_default`, `aws_s3_account_public_access_block` | on |
| Humans | `aws_iam_account_password_policy` | 14+ chars, reuse prevention 24 |
| Alerting | EventBridge rule → SNS | on GuardDuty findings severity ≥ 7 **and** on root account usage |

Inputs: `project`, `is_prod`, `alert_email`, `kms_key_arn` (or create via the kms-key module), `log_retention_days`.

## Tasks

1. Tests first (mocked): one run that asserts **every** control in the table exists, plus: trail `enable_log_file_validation = true`, `is_multi_region_trail = true`, password `minimum_password_length >= 14`, EventBridge pattern includes `"root"`.
2. Implement, wire into bootstrap.

## Acceptance

- [ ] Module tests pass with every control asserted
- [ ] Bootstrap calls `module "security_baseline"`

**Interview angle:** preventive vs detective controls, what you'd check first after a suspected breach (CloudTrail + GuardDuty), multi-account log archive design.

## Validate

```bash
git checkout -b ex/22-<short-name>
make exercise EX=22          # local: ✅/❌ per acceptance check
git push -u origin HEAD       # CI: the `exercise` workflow runs the same checks (strict) + every other pipeline
```
