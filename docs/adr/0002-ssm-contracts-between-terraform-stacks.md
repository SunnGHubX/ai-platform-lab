# ADR-0002: SSM Parameter Store contracts between Terraform stacks

- **Status:** Accepted
- **Date:** 2026-11-09

## Context

Terraform is split into `network → eks → services` stacks, each with its own state for blast-radius and speed. Downstream stacks need upstream IDs (VPC, subnets, cluster name, node SG).

## Decision

Producers publish values to `/<project>/<env>/<stack>/<key>` in SSM Parameter Store; consumers read them with `data "aws_ssm_parameter"`.

## Options considered

| Option | Pros | Cons |
|---|---|---|
| `terraform_remote_state` | Zero extra resources | Consumer needs read on the **whole** producer state (may hold secrets); tight coupling to backend layout |
| SSM parameters | Explicit, least-privilege contract; readable by non-Terraform tools (Helm, External Secrets, scripts) | Extra resources; producer must remember to publish |
| Data-source lookups by tag | No contract to maintain | Fragile, ambiguous matches, slow |
| Terragrunt `dependency` blocks | Elegant | Adds a tool; still reads state |

## Consequences

- Stacks must be applied in order the first time (`make apply-all`).
- Renaming a published key is a breaking change → version paths if needed.
- The same mechanism hands Terraform outputs to GitOps (`/services/<svc>/config`).
