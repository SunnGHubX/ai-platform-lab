# Study plan: from network/security/on-prem infra → AI platform / SRE / DevSecOps

You already have the hard-to-teach parts: 14 years of infra and IaC, a decade of hands-on security, physical data-center work, and on-prem GPU nodes for LLM testing. This plan builds the cloud-native layer on top, using this repo as the lab.

## Map your experience to the stack

| You've done | Maps to (what interviewers ask about) | Practice here |
|---|---|---|
| Cisco/Juniper/Arista, BGP, data-center fabrics | VPC design, EKS networking (VPC CNI, IP exhaustion), **RoCE/InfiniBand fabrics for GPU clusters**, NetworkPolicy | `terraform/modules/network`, `network/` (netgen), ex. 10–11 |
| Fortinet, hands-on security | DevSecOps: supply chain (SBOM, signing), policy-as-code, IAM least privilege, threat modelling | `policy/`, `.github/workflows/security.yaml`, ex. 05, 08, 09 |
| Ansible, Terraform, CI | Terraform **testing** & module design, GitOps, multi-env promotion | `terraform/`, `gitops/`, ex. 01–04 |
| On-prem GPU nodes for LLM testing (SkyHive) | GPU Operator, MIG/time-slicing, vLLM tuning, KV cache, autoscaling on queue depth | `ansible/roles/gpu_node`, `labs/07-vllm`, ex. 12 |
| eBay data centers, physical infra | Capacity planning, failure domains (AZ = rack/row), SLOs, incident response | `sre/`, `labs/10-chaos-engineering`, ex. 06–07, 13 |
| Startups (~7 yrs) | Ownership, cost awareness, pragmatic trade-offs → ADRs and design docs | `docs/adr/`, `templates/design-doc.md`, `study/interview/` |

## 8-week plan (≈ 6–8 h/week)

| Week | Focus | Do | Done when |
|---|---|---|---|
| 1 | GitOps foundations | Labs 01–02, ex. 04 | You can explain sync waves + self-heal and show an ApplicationSet |
| 2 | Terraform testing | Read `terraform/`, ex. 01–02 | Your new module feature has `terraform test` coverage and CI is green |
| 3 | Observability & SLOs | Labs 05–06, ex. 06 | A new SLO with burn-rate alerts **and** promtool tests |
| 4 | LLM serving | Labs 07–08, ex. 12 | You can tune vLLM (max-model-len, KV cache) and explain TTFT vs throughput |
| 5 | DevSecOps | ex. 05, 08, 09 | Image is signed, verified at admission, and a Rego policy blocks a bad manifest |
| 6 | Network-as-code for AI fabrics | ex. 10–11 | Fabric grows a spine without renumbering; golden tests updated deliberately |
| 7 | Reliability under failure | Lab 10, ex. 07, 13 | Game day run, postmortem written from the template |
| 8 | Interview sprint | `study/interview/` | Two mock system-design sessions recorded and reviewed |

## Security track (weeks 9–14, after the core plan)

| Week | Focus | Exercises | Done when |
|---|---|---|---|
| 9 | Encryption & data perimeter modules | 14, 15 | Buckets are only reachable from the VPC endpoint by named roles, with your CMK |
| 10 | Secrets never exposed | 17, 18, 26 | A planted secret fails CI; the leak drill runbook works end to end |
| 11 | Least privilege, IAM and K8s | 16, 19 | No `AdministratorAccess`; `kubectl auth can-i` matrix passes |
| 12 | Zero trust in the cluster | 20, 21 | Default-deny proven by e2e; vLLM accepts only the gateway's SPIFFE identity |
| 13 | Account & org guardrails | 22, 23, 24 | Every account has the baseline; SCPs tested; CI actions SHA-pinned |
| 14 | Capstone | 25 | Five attack simulations from a "compromised" pod all fail in e2e |

Your edge here: a decade of hands-on security (Fortinet, segmentation, firewall policy) maps directly onto zero trust (default-deny, identity-based policy), data perimeters, and SCP "ceilings". Use that vocabulary in interviews.

## How to work each exercise

1. Branch: `git checkout -b ex/NN-short-name`.
2. **Write the test first** (`terraform test`, `pytest`, `conftest verify`, `promtool test rules`).
3. Implement until green locally, open a PR, let CI prove it.
4. Write a 5-line ADR or PR description: what, why, trade-offs. That's your interview story.

## Run every test suite locally

```bash
make -C terraform test                                     # terraform test (mocked AWS)
(cd network && pytest)                                     # netgen
(cd services/inference-gateway && pytest)                  # service
docker run --rm -v "$PWD:/p" -w /p openpolicyagent/conftest verify --policy policy/kubernetes
docker run --rm -v "$PWD:/p" -w /p/sre/slo/tests --entrypoint promtool prom/prometheus test rules inference-slo.test.yaml
(cd ansible && ansible-lint)
```
