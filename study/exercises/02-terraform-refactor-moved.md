# 02 · Rename resources without destroying them ★★

**Scenario:** `aws_s3_bucket.this` in the microservice module should become `aws_s3_bucket.data` (a second bucket type is coming). In prod, a destroy/recreate would delete MLflow's artifacts.

## Tasks

1. Rename the resource and all references.
2. Add `moved { from = aws_s3_bucket.this  to = aws_s3_bucket.data }` (and for every dependent resource).
3. Because the module is called with `for_each` in the `services` stack, verify the address works for **every** instance (`module.service["mlflow"].aws_s3_bucket.data`).
4. Add a `terraform test` run with `command = plan` that proves no bucket is planned for destroy. (Hint: you can't easily test `moved` with mocks, so document the manual `terraform plan` check in the PR instead, and explain why.)

## Acceptance

- [ ] `terraform plan` on an existing state shows `has moved to`, **0 to destroy**
- [ ] PR description explains `moved` vs `terraform state mv` vs `import` blocks

**Interview angle:** safe refactoring of shared modules used by many teams; why `moved` blocks beat `state mv` in a GitOps/CI world.
