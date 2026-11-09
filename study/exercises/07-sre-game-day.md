# 07 · Game day: break vLLM under load, write the postmortem ★★★

## Tasks

1. Run `labs/10-chaos-engineering` experiments 01, 02 and 04 under `scripts/loadtest.py` load.
2. Record: time of fault, first alert, mitigation, recovery.
3. Compute the error-budget cost of each experiment from Prometheus (`slo:gateway_errors:ratio_rate1h` × duration).
4. Write a postmortem with `templates/postmortem.md` for the worst one, with at least three action items (prevent / detect / mitigate).
5. Implement one action item (e.g. a `PodDisruptionBudget` for vLLM, a readiness gate, or a gateway retry with budget).

## Acceptance

- [ ] `docs/postmortems/YYYY-MM-DD-<name>.md` merged
- [ ] One action item shipped with a test

**Interview angle:** "Tell me about an incident you handled." This gives you a fresh, detailed, data-backed story.

## Validate

```bash
git checkout -b ex/07-<short-name>
make exercise EX=07          # local: ✅/❌ per acceptance check
git push -u origin HEAD       # CI: the `exercise` workflow runs the same checks (strict) + every other pipeline
```
