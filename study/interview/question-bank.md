# Question bank

Answer out loud in ≤ 2 minutes each, then check the repo for a concrete example you can point to.

## Terraform / IaC
1. How do you structure Terraform for many environments without copy-paste? *(stacks + envs tfvars; `terraform/README.md`)*
2. Remote state vs SSM/data contracts between stacks: trade-offs? *(ADR-0002)*
3. How do you test Terraform? *(mock providers, `terraform test`, variable validation, checkov)*
4. How do you refactor a module used by 30 teams safely? *(`moved` blocks, versioned modules, plan in CI)*
5. How do you keep secrets out of state? *(RDS-managed passwords, Secrets Manager containers, ephemeral resources)*

## Kubernetes / GitOps
6. Walk through what happens when you `git push` a change to `platform/vllm`.
7. Why sync waves? What breaks without them?
8. Requests vs limits for GPUs and memory: what's different about extended resources?
9. How does a pod get AWS credentials with Pod Identity vs IRSA?
10. Design NetworkPolicies for a model-serving namespace.

## SRE
11. Define SLI, SLO, SLA, error budget. Why 99.5% and not 99.99%?
12. Explain multi-window multi-burn-rate alerting. Why 14.4?
13. Cause-based vs symptom-based alerts: which page?
14. Walk me through your last incident (use your game-day postmortem).
15. How do you reduce toil on a platform team?

## DevSecOps
16. What's in your CI security pipeline, and what does each stage catch?
17. SBOM: what is it, who consumes it, what format?
18. Keyless signing: what are Fulcio and Rekor, and what does verification check?
19. Shift-left (Conftest in CI) vs admission control (Gatekeeper/Kyverno): why both?
20. How would you threat-model the inference gateway? (STRIDE)

## AI infrastructure
21. TTFT vs inter-token latency vs throughput: which knobs move which?
22. What limits vLLM concurrency on a single GPU? *(KV cache)*
23. MIG vs time-slicing vs separate GPUs.
24. Why do GPU clusters need lossless networking? PFC vs ECN?
25. How would you autoscale an LLM service, and what's special about cold starts?

## Networking (your edge)
26. eBGP Clos underlay: why unique ASNs per leaf and shared on spines?
27. ECMP hashing and elephant flows in AI training traffic.
28. VPC CNI IP exhaustion on EKS: symptoms and fixes (prefix delegation, secondary CIDRs, custom networking).
29. Design connectivity from on-prem GPU clusters to AWS (Direct Connect, TGW, routing, failover).
30. Troubleshoot intermittent packet loss that only affects large transfers. *(MTU/PMTUD, jumbo frames mismatch)*
