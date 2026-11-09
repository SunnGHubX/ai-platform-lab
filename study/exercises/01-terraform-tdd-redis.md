# 01 · Add an ElastiCache (Redis) feature to the service catalog, TDD-style ★★

**Scenario:** the inference-gateway needs a shared rate limiter across pods (the in-memory one is per pod). Product wants `redis = { node_type = "cache.t4g.small" }` in the service catalog.

## Tasks

1. **Test first.** In `terraform/modules/microservice/tests/microservice.tftest.hcl` add runs that assert:
   - no `redis` → no ElastiCache resources;
   - `redis = {}` → a replication group with `transit_encryption_enabled = true`, `at_rest_encryption_enabled = true`, in the private subnets, SG allowing 6379 **only** from the node SG;
   - prod → `automatic_failover_enabled = true` and `num_cache_clusters >= 2`.
2. Run `make -C terraform test` and watch them fail.
3. Implement: `variable "redis"` (nullable object with `optional()` defaults), `aws_elasticache_subnet_group`, `aws_security_group` + ingress rule, `aws_elasticache_replication_group`. Add `redis` to the `services` stack variable type and pass it through.
4. Add a cross-variable validation in `stacks/services`: in prod, `redis.multi_az` must be true.
5. Publish the endpoint in the `service_config` SSM JSON.

## Acceptance

- [ ] `terraform test` green for `modules/microservice` and `stacks/services`
- [ ] `checkov` shows no new HIGH findings for the new resources
- [ ] `envs/dev/services.tfvars` enables Redis for `inference-gateway`

<details><summary>Hints</summary>

- `aws_elasticache_replication_group` needs `auth_token` *or* RBAC users for in-transit encryption. Prefer `auth_token` from Secrets Manager via `manage_...`? (It doesn't exist for ElastiCache; think about how to keep it out of state, e.g. `ephemeral` resources in Terraform ≥ 1.10 or write-only args in ≥ 1.11.)
- Mock providers don't validate argument combinations; your asserts are the contract.
</details>

**Interview angle:** "How do you test Terraform?" Answer with mock providers, plan-time assertions, policy validations, and why you don't need real AWS to test module contracts.
