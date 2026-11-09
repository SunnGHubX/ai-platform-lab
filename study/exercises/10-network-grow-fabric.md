# 10 · Grow the fabric: third spine + border leaf ★★

**Scenario:** the GPU pod is growing. Add `spine3` and a `border-leaf1` that peers with the firewall / internet edge.

## Tasks

1. Add `spine3` to `network/fabric/fabric.yaml`. Run the tests. Which fail and **why**? (Hint: `stride` = pool /31s ÷ spines; is your pool big enough? Do existing link IPs change? Should they?)
2. Fix the model so adding a spine **never renumbers existing links** (e.g. a fixed per-spine block size declared in the YAML). Write the test first.
3. Add `role: border` leaves: extra eBGP session to an external ASN with a prefix-list that only advertises a default route inward and the server subnets outward.
4. Update golden files deliberately (`UPDATE_GOLDEN=1 pytest`) and review the diff like a change ticket.

## Acceptance

- [ ] `pytest network` green, including a new "adding a spine does not renumber" test
- [ ] Border leaf config has inbound/outbound route policy

**Interview angle:** Clos design, ECMP, failure domains, why deterministic addressing matters for automation.

## Validate

```bash
git checkout -b ex/10-<short-name>
make exercise EX=10          # local: ✅/❌ per acceptance check
git push -u origin HEAD       # CI: the `exercise` workflow runs the same checks (strict) + every other pipeline
```
