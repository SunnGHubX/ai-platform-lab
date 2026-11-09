# 23 · Organization guardrails: SCPs as code ★★★

**Track:** Security · least privilege at org scale · **Complex**

**Scenario:** Even with perfect IAM inside each account, an account admin can disable CloudTrail, leave the organization, or launch GPUs in a region you don't monitor. **Service Control Policies** are the ceiling no one in the account can raise.

## Requirements

`terraform/modules/org-guardrails/` (applied from an `envs/_global/organization` root you create):

SCPs (each its own `aws_organizations_policy`, with `sid`s):
1. `DenyLeaveOrganization`
2. `DenyDisableSecurityServices`: CloudTrail Stop/Delete/Update, GuardDuty Delete/Disassociate, Config Stop/Delete, SecurityHub Disable, AccessAnalyzer Delete
3. `DenyRootUser`: `aws:PrincipalArn` like `arn:aws:iam::*:root`
4. `RegionAllowList`: deny outside `var.allowed_regions` except global services (same list as exercise 16)
5. `DenyUnencryptedUploads` / `RequireIMDSv2` (`ec2:MetadataHttpTokens` must be `required` on RunInstances)
6. `ProtectSecurityRoles`: deny modifying roles tagged `security-baseline=true` unless principal tagged `security-admin=true`

Attach to OUs from `var.ou_ids` with `aws_organizations_policy_attachment`. Prod OU gets an extra SCP: `DenyGPUInstancesOutsideApprovedTypes` (allow only `g6e.*`, `p5.*`).

## Tasks

1. Tests first: every SCP `sid` present; JSON size < 5120 chars (the SCP limit, assert with `length(jsonencode(...))`); prod-only SCP attached only to the prod OU.
2. Write a **policy simulator** step in the exercise notes (`aws iam simulate-custom-policy`) for at least two deny cases.

## Acceptance

- [ ] Module with ≥ 6 SCP statements and tests
- [ ] Size-limit assertion in tests

**Interview angle:** SCP vs permission boundary vs IAM policy evaluation order, why SCPs never grant, how to test SCPs safely (sandbox OU first).

## Validate

```bash
git checkout -b ex/23-<short-name>
make exercise EX=23          # local: ✅/❌ per acceptance check
git push -u origin HEAD       # CI: the `exercise` workflow runs the same checks (strict) + every other pipeline
```
