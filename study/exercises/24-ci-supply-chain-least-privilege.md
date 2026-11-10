# 24 · Least-privilege CI: harden every GitHub Actions workflow ★★

**Track:** Security · DevSecOps · **Common scenario**

**Scenario:** CI is the most privileged identity you have: it can push images, sign them and assume AWS roles. A malicious dependency in a test, or a compromised third-party Action, inherits all of that.

## Requirements

1. Every workflow has **top-level** `permissions: contents: read` (or `{}`) and escalates only per job.
2. Every third-party Action (not `actions/*` or `github/*`) is **pinned to a full commit SHA** with a `# vX.Y.Z` comment. Dependabot keeps SHAs updated.
3. No `pull_request_target`, no `${{ github.event.*.body/title }}` interpolated into `run:` (script injection).
4. AWS OIDC: tighten `terraform/envs/_global/bootstrap` plan-role trust from `repo:...:pull_request` to also require `job_workflow_ref` of `terraform-plan.yaml` (so another workflow in the repo can't assume it).
5. A test `tests/ci/test_workflows.py` (pytest) that parses `.github/workflows/*.yaml` and enforces rules 1–3. Run it in `validate.yaml`.

## Acceptance

- [ ] `tests/ci/test_workflows.py` exists, runs in CI, passes
- [ ] All third-party `uses:` pinned to 40-char SHAs
- [ ] OIDC trust includes `job_workflow_ref`

<details><summary>Hints</summary>

- Script injection: `run: echo "${{ github.event.pull_request.title }}"` lets a PR title execute code. Pass through `env:` instead.
- `yaml.safe_load` turns the `on:` key into Python `True`. Handle that in your test!
</details>

**Interview angle:** SLSA build integrity, tj-actions/changed-files style incidents, OIDC subject claims, why pinning tags isn't enough.

## Validate

```bash
git checkout -b ex/24-<short-name>
make exercise EX=24          # local: ✅/❌ per acceptance check
git push -u origin HEAD       # CI: the `exercise` workflow runs the same checks (strict) + every other pipeline
```
