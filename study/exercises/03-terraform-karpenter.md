# 03 · Replace the GPU managed node group with Karpenter ★★★★

**Scenario:** GPU Spot capacity is patchy and the team wants to try g6, g6e, g5 and p4d sizes automatically. Managed node groups can't do "any of these, cheapest available".

## Tasks

1. Add the Karpenter submodule from `terraform-aws-modules/eks/aws//modules/karpenter` (controller IAM, SQS interruption queue, node IAM role, Pod Identity).
2. Install Karpenter via Argo CD (new `gitops/apps/karpenter.yaml`), chart version pinned.
3. Write a `NodePool` + `EC2NodeClass` for GPUs: `karpenter.k8s.aws/instance-gpu-manufacturer: nvidia`, taint `nvidia.com/gpu=true:NoSchedule`, `consolidationPolicy: WhenEmpty` (why not `WhenEmptyOrUnderutilized` for model servers?).
4. Keep the `system` managed node group (Karpenter itself must not run on Karpenter nodes).
5. Delete the GPU managed node group and the ASG tag workaround. Write an ADR explaining the trade-off.

## Acceptance

- [ ] `terraform validate` / `test` green; new Argo app syncs in a kind cluster (CRDs only)
- [ ] ADR-0003 written: Cluster Autoscaler + MNG vs Karpenter for GPU workloads
- [ ] Load test triggers a GPU node launch and scale-down after cooldown (real cluster, optional)

**Interview angle:** GPU cost control, Spot interruption handling, bin-packing vs model-loading time.
