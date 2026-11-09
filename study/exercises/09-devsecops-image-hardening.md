# 09 · Drive image CVEs to zero ★★

## Tasks

1. Run `trivy image` on the current gateway image; save the HIGH/CRITICAL count.
2. Switch the runtime stage to a minimal base (e.g. `gcr.io/distroless/python3-debian12:nonroot` or a Chainguard Python image). Watch out: no shell, so `ENTRYPOINT` must be exec-form and the venv/site-packages path must match the base's Python.
3. Compare size, CVE count and startup time. Put the table in the PR.
4. Add `--exit-code 1 --severity HIGH,CRITICAL --ignore-unfixed` to the CI gate once you're at zero.

## Acceptance

- [ ] CI passes with the stricter gate
- [ ] Image size and CVE count reduced; documented

**Interview angle:** base-image strategy, patch SLAs, the difference between "fixable" and "all" CVEs.

## Validate

```bash
git checkout -b ex/09-<short-name>
make exercise EX=09          # local: ✅/❌ per acceptance check
git push -u origin HEAD       # CI: the `exercise` workflow runs the same checks (strict) + every other pipeline
```
