# 26 · Incident drill: an AWS access key leaked in a public commit ★★

**Track:** Security · incident response · **Common scenario (it happens constantly)**

**Scenario:** 10:02 a contractor pushes a commit containing `AKIA…` and its secret to a public repo. 10:05 GitHub secret scanning alerts. 10:09 GuardDuty reports `UnauthorizedAccess:IAMUser/InstanceCredentialExfiltration` in us-east-1, a region you don't use, launching `p4d.24xlarge` instances.

## Requirements

1. **Runbook** `docs/runbooks/LeakedAWSCredentials.md` using `templates/runbook.md`, with real commands for:
   - contain: deactivate the key, attach an inline **deny-all with `aws:TokenIssueTime` condition** to revoke already-issued sessions, quarantine the IAM user
   - scope: CloudTrail Lake/Athena queries for everything the key did (by `userIdentity.accessKeyId`) in all regions
   - eradicate: terminate attacker resources (all regions), delete created IAM users/keys/roles
   - recover: rotate everything the user could read (Secrets Manager, SSM)
   - Git: remove from history (`git filter-repo`), but **the key is compromised regardless**; rotation is what matters
2. **Prevention as code:** a reusable Terraform snippet/module `terraform/modules/revoke-sessions/` that renders the `aws:TokenIssueTime` deny policy for a given role/user and timestamp (with a test).
3. **Postmortem** in `docs/postmortems/` from the template, treating the drill as real (timeline, contributing factors: why did a human have long-lived keys at all?).

## Acceptance

- [ ] Runbook with contain/scope/eradicate/recover sections and the `aws:TokenIssueTime` command
- [ ] `revoke-sessions` module + test
- [ ] Postmortem whose action items include removing long-lived IAM user keys

**Interview angle:** the first 15 minutes of a credential leak, why deleting the commit doesn't help, why OIDC/SSO everywhere makes this class of incident disappear.

## Validate

```bash
git checkout -b ex/26-<short-name>
make exercise EX=26          # local: ✅/❌ per acceptance check
git push -u origin HEAD       # CI: the `exercise` workflow runs the same checks (strict) + every other pipeline
```
