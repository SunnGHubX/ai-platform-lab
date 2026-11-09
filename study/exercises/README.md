# Exercises

Graded ★ (an evening) to ★★★★ (a weekend). Each one has acceptance criteria that are **checked automatically**, so you know when you're done:

```bash
make exercises            # status board: ⬜/✅ for every exercise
make exercise EX=06       # detailed ✅/❌ per check for one exercise
```

Work on a branch named `ex/NN-<anything>` and push: the `exercise` workflow runs that exercise's checks in CI (strict mode, so a missing tool is a failure) and writes the ✅/❌ table to the run summary. All other pipelines (unit tests, policies, security, e2e) run too, so solving an exercise can't quietly break the platform. The checks live in [`study/checks/exercises.yaml`](../checks/exercises.yaml).

| # | Exercise | Area | Level |
|---|---|---|---|
| 01 | [Add an ElastiCache (Redis) feature to the service catalog, TDD-style](01-terraform-tdd-redis.md) | Terraform | ★★ |
| 02 | [Rename resources without destroying them (`moved` blocks)](02-terraform-refactor-moved.md) | Terraform | ★★ |
| 03 | [Replace managed node groups with Karpenter for GPUs](03-terraform-karpenter.md) | Terraform / K8s | ★★★★ |
| 04 | [ApplicationSet: one template, three environments](04-gitops-applicationset.md) | GitOps | ★★★ |
| 05 | [Write Rego policies: approved registries + PDBs](05-policy-as-code.md) | DevSecOps | ★★ |
| 06 | [A TTFT SLO with burn-rate alerts and promtool tests](06-sre-ttft-slo.md) | SRE | ★★★ |
| 07 | [Game day: break vLLM under load, write the postmortem](07-sre-game-day.md) | SRE | ★★★ |
| 08 | [Enforce signed images at admission (Kyverno verifyImages)](08-devsecops-signed-images.md) | DevSecOps | ★★★ |
| 09 | [Drive image CVEs to zero (distroless / chainguard)](09-devsecops-image-hardening.md) | DevSecOps | ★★ |
| 10 | [Grow the fabric: third spine + border leaf, no renumbering](10-network-grow-fabric.md) | Network | ★★ |
| 11 | [EVPN-VXLAN overlay templates](11-network-evpn-vxlan.md) | Network | ★★★★ |
| 12 | [Share GPUs: MIG and time-slicing with the GPU Operator](12-gpu-sharing.md) | GPU / K8s | ★★★ |
| 13 | [Troubleshooting drills (interview-style)](13-troubleshooting-drills.md) | All | ★★ → ★★★★ |
