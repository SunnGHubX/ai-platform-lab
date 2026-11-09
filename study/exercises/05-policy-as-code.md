# 05 · Write Rego policies: approved registries + PDBs ★★

## Tasks

1. In `policy/kubernetes/`, add `deny` rules:
   - images must come from `ghcr.io/sunnghubx/`, `nvcr.io/nvidia/`, `vllm/`, `ghcr.io/mlflow/` (allow-list in a `data` file, not hard-coded);
   - a Deployment with `replicas > 1` must have a matching PodDisruptionBudget. (Conftest evaluates documents separately: use `conftest test --combine` and rewrite the rule over `input[_]`.)
2. Write `test_` cases for allow and deny for each rule **before** implementing.
3. Run `conftest verify` and `conftest test` against every `platform/*` build.

## Acceptance

- [ ] `conftest verify` green with ≥ 4 new tests
- [ ] CI policy job passes on `platform/`

**Interview angle:** shift-left vs admission-time enforcement; why you run the *same* Rego in CI (Conftest) and in-cluster (Gatekeeper).

## Validate

```bash
git checkout -b ex/05-<short-name>
make exercise EX=05          # local: ✅/❌ per acceptance check
git push -u origin HEAD       # CI: the `exercise` workflow runs the same checks (strict) + every other pipeline
```
