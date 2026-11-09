# 21 · Workload identity + mTLS: authorize by *who*, not *where* ★★★★

**Track:** Security · zero trust · **Complex**

**Scenario:** NetworkPolicies (exercise 20) trust IP ranges and labels. Anyone who can create a pod labelled `app.kubernetes.io/name: inference-gateway` passes them. Zero trust means **authenticate every connection with a cryptographic workload identity** and authorize on that identity.

## Requirements

1. Install a service mesh via Argo CD: **Istio ambient** (`gitops/apps/istio.yaml`) *or* Linkerd. Pin chart versions. Write an ADR (`docs/adr/0004-*.md`) explaining your choice and the sidecar-vs-ambient trade-off for GPU pods.
2. Enforce **STRICT mTLS** in `inference` (`PeerAuthentication` mode STRICT, or Linkerd's `config.linkerd.io/default-inbound-policy: all-authenticated`).
3. `AuthorizationPolicy` on vLLM: allow only principal `cluster.local/ns/inference/sa/inference-gateway` (SPIFFE identity), plus Prometheus scraping. Everything else is denied.
4. Show it in a test: a pod with the **same labels** as the gateway but a different ServiceAccount is denied (L7 403 / connection reset).

## Acceptance

- [ ] Mesh Argo CD app + ADR-0004
- [ ] STRICT mTLS for `inference`
- [ ] AuthorizationPolicy referencing the gateway's SPIFFE identity

**Interview angle:** SPIFFE/SPIRE, mTLS vs network segmentation, identity-based authz, overhead of meshes on high-throughput inference traffic.

## Validate

```bash
git checkout -b ex/21-<short-name>
make exercise EX=21          # local: ✅/❌ per acceptance check
git push -u origin HEAD       # CI: the `exercise` workflow runs the same checks (strict) + every other pipeline
```
