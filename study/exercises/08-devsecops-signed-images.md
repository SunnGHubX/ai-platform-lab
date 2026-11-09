# 08 · Enforce signed images at admission ★★★

**Scenario:** the pipeline already signs `inference-gateway` with cosign keyless. Nothing *checks* the signature, so it's theatre until admission enforces it.

## Tasks

1. Install Kyverno via Argo CD (`gitops/apps/kyverno.yaml`, pinned chart).
2. Write a `ClusterPolicy` with `verifyImages` for `ghcr.io/sunnghubx/*`: keyless attestor with `subject` regexp `https://github.com/SunnGHubX/ai-platform-lab/.github/workflows/inference-gateway.yaml@refs/heads/main` and issuer `https://token.actions.githubusercontent.com`.
3. Also require the CycloneDX attestation to exist.
4. Prove it: deploy an unsigned image with the same name in a test namespace → rejected.
5. Use the Kyverno CLI (`kyverno test`) in CI with a fixture for allow + deny.

## Acceptance

- [ ] Unsigned image rejected, signed image admitted (screenshot / log in PR)
- [ ] `kyverno test` job in CI

**Interview angle:** SLSA levels, keyless signing (Fulcio/Rekor), why signing without verification is useless.
