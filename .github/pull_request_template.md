## What & why

<!-- one paragraph -->

## Type
- [ ] Platform (GitOps / manifests)
- [ ] Terraform (env: dev / staging / prod)
- [ ] Service code
- [ ] Policy / security
- [ ] SRE (SLOs, alerts, runbooks)
- [ ] Docs / study

## Checklist
- [ ] Tests added or updated (`terraform test`, `pytest`, `conftest verify`, `promtool test rules`)
- [ ] `make -C terraform plan` output reviewed for every affected env (Terraform changes)
- [ ] New alerts have a runbook in `docs/runbooks/`
- [ ] No secrets, account IDs or internal hostnames added
- [ ] Rollback plan: <!-- revert commit / feature flag / manual steps -->
