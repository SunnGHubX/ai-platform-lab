# 14 · Custom module: `kms-key` with a least-privilege key policy ★

**Track:** Security · Terraform modules · **Common scenario**

**Scenario:** Every team creates KMS keys differently. Some keys have `"Principal": "*"` with `kms:*`, some never rotate, and nobody can tell who's allowed to decrypt. Security asks for **one module** every stack must use.

## Requirements

Create `terraform/modules/kms-key/` with this interface:

| Input | Type | Notes |
|---|---|---|
| `alias` | string | becomes `alias/<alias>`; validated `^[a-z0-9/_-]+$` |
| `description` | string | |
| `admin_role_arns` | list(string) | may manage the key, **may not** use it to decrypt |
| `usage_role_arns` | list(string) | may `Encrypt/Decrypt/GenerateDataKey*/DescribeKey`, nothing else |
| `service_principals` | list(string) | e.g. `logs.us-west-2.amazonaws.com`, scoped with `aws:SourceAccount` |
| `is_prod` | bool | prod → `deletion_window_in_days = 30`, else 7 |

Outputs: `key_arn`, `key_id`, `alias_arn`.

Rules the key policy must follow:
1. Separate **admin** and **usage** statements. Admins never get `kms:Decrypt`.
2. The account root statement exists (so the key can't be orphaned), but **only** for `kms:*` management through IAM, which is the AWS-recommended pattern. Explain in a comment why it's still needed.
3. No statement anywhere has `Principal = "*"` without a condition.
4. `enable_key_rotation = true` always.

## Tasks

1. **Tests first:** `terraform/modules/kms-key/tests/kms_key.tftest.hcl` with mocked AWS. Assert rotation, deletion window per env, alias format validation (`expect_failures`), and that the rendered policy has no `kms:Decrypt` in the admin statement. (Tip: build the policy with `aws_iam_policy_document` and assert on its `statement` blocks, the same trick used in `microservice` tests.)
2. Implement the module.
3. Use it: replace the inline `aws_kms_key` in `modules/state-backend`.

## Acceptance

- [ ] `make -C terraform test` passes, with ≥ 5 runs in the new test file
- [ ] `state-backend` uses `module "kms"` (no inline `aws_kms_key`)
- [ ] checkov: no new findings for KMS (`CKV2_AWS_64` key policy defined is now satisfied)

<details><summary>Hints</summary>

- `data "aws_iam_policy_document"` + `dynamic "statement"` lets you skip the usage statement when `usage_role_arns` is empty.
- Service principals: add `condition { test = "StringEquals" variable = "aws:SourceAccount" values = [account_id] }` to stop the confused-deputy problem.
</details>

**Interview angle:** key policies vs IAM policies (KMS is the one service where the resource policy must allow access), separation of duties, confused deputy.

## Validate

```bash
git checkout -b ex/14-<short-name>
make exercise EX=14          # local: ✅/❌ per acceptance check
git push -u origin HEAD       # CI: the `exercise` workflow runs the same checks (strict) + every other pipeline
```
