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

## Security track: zero trust, least privilege, RBAC, no exposed secrets

Common scenarios (★–★★) are what you'll do in week one of a platform/security role; complex ones (★★★–★★★★) are senior/staff interview material. Modules build on each other: **14 → 15 → 22**, **16 → 23**, **20 → 21 → 25**.

| # | Exercise | Theme | Level |
|---|---|---|---|
| 14 | [Custom module: `kms-key` with a least-privilege key policy](14-tf-module-kms-key.md) | Terraform module · encryption | ★ |
| 15 | [Custom module: `secure-bucket` with a data perimeter](15-tf-module-secure-bucket.md) | Terraform module · zero trust for data | ★★ |
| 16 | [Permissions boundaries + replace the admin CI role](16-tf-permissions-boundary.md) | Least privilege · IAM escalation | ★★★ |
| 17 | [No secrets in Terraform state or tfvars](17-tf-no-secrets-in-state.md) | Secrets · ephemeral / write-only | ★★ |
| 18 | [No Secret manifests in Git: External Secrets Operator](18-k8s-external-secrets.md) | Secrets · Kubernetes | ★★ |
| 19 | [Kubernetes RBAC least privilege + EKS access entries](19-k8s-rbac-least-privilege.md) | RBAC | ★★ |
| 20 | [Zero-trust networking: default-deny everywhere](20-zero-trust-network-policies.md) | Zero trust · proven on kind | ★★★ |
| 21 | [Workload identity + mTLS: authorize by *who*, not *where*](21-zero-trust-mtls-identity.md) | Zero trust · SPIFFE | ★★★★ |
| 22 | [Custom module: `security-baseline` for every AWS account](22-tf-security-baseline-module.md) | Terraform module · detective controls | ★★★ |
| 23 | [Organization guardrails: SCPs as code](23-tf-org-guardrails-scp.md) | Least privilege at org scale | ★★★ |
| 24 | [Least-privilege CI: harden every GitHub Actions workflow](24-ci-supply-chain-least-privilege.md) | Supply chain | ★★ |
| 25 | [Red-team: "the gateway pod is compromised"](25-red-team-compromised-pod.md) | Capstone · assume breach | ★★★★ |
| 26 | [Incident drill: an AWS key leaked in a public commit](26-incident-leaked-credentials.md) | Incident response | ★★ |
