# 15 · Custom module: `secure-bucket` with a data perimeter ★★

**Track:** Security · Terraform modules · zero trust for data

**Scenario:** An auditor found that the MLflow artifact bucket is readable by *any* principal in the account that has `s3:GetObject *`, including over the public internet with stolen credentials. Requirement: **bucket data is reachable only from inside our VPC, by named roles, encrypted with our CMK.**

## Requirements

Create `terraform/modules/secure-bucket/`:

| Input | Notes |
|---|---|
| `name` | full bucket name |
| `kms_key_arn` | CMK from exercise 14 (SSE-KMS, bucket key on) |
| `reader_role_arns`, `writer_role_arns` | the only principals allowed |
| `allowed_vpce_ids` | requests must come through these VPC endpoints (`aws:SourceVpce`) |
| `access_log_bucket` | server access logging target |
| `is_prod` | prod → versioning required, `force_destroy = false`, Object Lock optional input `object_lock_days` |

Bucket policy must contain **deny** statements for:
1. `aws:SecureTransport = false`
2. `s3:PutObject` without `aws:kms` SSE, or with a **different** KMS key (`s3:x-amz-server-side-encryption-aws-kms-key-id`)
3. Any request **not** from `allowed_vpce_ids`, **except** for principals tagged as break-glass (`aws:PrincipalTag/break-glass = true`). Think about why you need an escape hatch.
4. Any principal not in reader/writer lists (`aws:PrincipalArn` `ArnNotLike`), with the same break-glass exception.

## Tasks

1. Tests first (mocked): one run per deny statement asserting its `sid` exists; prod vs dev differences; `expect_failures` when `allowed_vpce_ids` is empty in prod.
2. Implement, then refactor `modules/microservice` to call `secure-bucket` instead of its inline S3 resources (use `moved` blocks, see exercise 02).
3. Pass the S3 gateway endpoint ID from the network stack via SSM (`/network/s3_vpce_id`).

## Acceptance

- [ ] New module tests pass; `microservice` tests still pass
- [ ] `microservice/main.tf` has no `resource "aws_s3_bucket"` left
- [ ] Network stack publishes `s3_vpce_id`

<details><summary>Hints</summary>

- `aws:SourceVpce` only works for traffic through a VPC endpoint; console access stops working. That's the point, and it's why break-glass exists.
- Deny + `StringNotEquals` on a *list* uses `ForAnyValue`/`ForAllValues` carefully; for a single-valued key like `aws:SourceVpce`, plain `StringNotEquals` is correct.
</details>

**Interview angle:** AWS data perimeters (identity, resource, network), why "deny unless" beats "allow if", how you'd roll this out without breaking prod (start in log-only via Access Analyzer).

## Validate

```bash
git checkout -b ex/15-<short-name>
make exercise EX=15          # local: ✅/❌ per acceptance check
git push -u origin HEAD       # CI: the `exercise` workflow runs the same checks (strict) + every other pipeline
```
