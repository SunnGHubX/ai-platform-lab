# 17 · No secrets in Terraform state or tfvars ★★

**Track:** Security · secrets · **Common scenario**

**Scenario:** Someone runs `terraform state pull | grep -i password` in a review and finds a database password and an ElastiCache auth token in plaintext. State lives in S3, readable by every CI plan role. Fix it so **no secret value ever enters state, plan files, tfvars or logs**.

## Requirements

1. Use **ephemeral resources** (Terraform ≥ 1.10) to generate secrets: `ephemeral "random_password"`.
2. Pass them only to **write-only arguments** (Terraform ≥ 1.11), e.g. `password_wo` + `password_wo_version` on RDS, `secret_string_wo` on `aws_secretsmanager_secret_version`.
3. Rotation: bumping `*_wo_version` rotates the secret.
4. A guard test: a Python test `terraform/tests/test_no_secrets.py` (pytest) that scans `terraform/**/*.tf` and `*.tfvars` and fails on:
   - `password|secret|token|api_key` assigned a string literal
   - any non-ephemeral `resource "random_password"`
   - any `output` whose name matches those words without `sensitive = true`
5. Run that test in CI (add it to `validate.yaml` → terraform job).

## Tasks

1. Write `test_no_secrets.py` first and run it: it should pass today (nothing leaks yet). Then **plant** a leak in a scratch branch to prove it fails.
2. Add an optional `auth_token` path for exercise 01's Redis (or a new `api-keys` secret for `inference-gateway`) using ephemeral + write-only.
3. Document in `terraform/README.md` → "Secrets" section.

## Acceptance

- [ ] `ephemeral "random_password"` used at least once; `_wo` arguments used
- [ ] No `resource "random_password"` anywhere
- [ ] `test_no_secrets.py` exists and runs in CI

<details><summary>Hints</summary>

- `manage_master_user_password = true` (already used for RDS) is the other good pattern: AWS generates and rotates, Terraform never sees it.
- `sensitive = true` hides values from CLI output but **they're still in state**. That's the misconception this exercise targets.
</details>

**Interview angle:** where secrets leak in IaC (state, plan, logs, tfvars, CI artifacts), ephemeral vs sensitive, rotation without downtime.

## Validate

```bash
git checkout -b ex/17-<short-name>
make exercise EX=17          # local: ✅/❌ per acceptance check
git push -u origin HEAD       # CI: the `exercise` workflow runs the same checks (strict) + every other pipeline
```
