# Security

## Reporting a vulnerability

Please **do not open a public issue**. Use GitHub's *Report a vulnerability* (Security → Advisories) on this repository. You'll get an acknowledgement within 3 business days.

## What this repo does to stay secure

| Layer | Control | Where |
|---|---|---|
| Source | Secret scanning on full history (gitleaks), pre-commit hooks | `.github/workflows/security.yaml`, `.pre-commit-config.yaml` |
| Code | CodeQL (Python + Actions), ruff `S` (bandit) rules | `codeql.yaml`, `services/*/pyproject.toml` |
| Dependencies | Dependabot (actions, pip, docker, terraform), Trivy fs scan | `.github/dependabot.yml` |
| IaC | checkov + Trivy config on Terraform & manifests, tflint | `validate.yaml`, `security.yaml` |
| Kubernetes | OPA/Conftest policies (no `:latest`, limits, no privileged, GPU tolerations) with unit tests | `policy/kubernetes/` |
| Images | Multi-stage non-root builds, Trivy image scan gate, CycloneDX SBOM | `inference-gateway.yaml` |
| Supply chain | cosign keyless signatures + SBOM attestations via GitHub OIDC | `inference-gateway.yaml` |
| Cloud | No static AWS keys (GitHub OIDC), per-service least-privilege IAM via Pod Identity, `allowed_account_ids` | `terraform/` |
| Runtime | NetworkPolicy, PDB, read-only root FS, dropped capabilities, seccomp RuntimeDefault | `platform/inference-gateway/` |

## Scope note

This is a learning lab. The bootstrap Terraform apply role uses `AdministratorAccess` for simplicity, which is flagged by checkov on purpose. Replace it with a scoped policy and a permissions boundary before using this pattern for real.
