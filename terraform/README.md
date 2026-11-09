# Terraform — AWS foundation for the Sunn Platform Lab

This provisions what the GitOps layer runs **on**: an account-isolated VPC, an EKS cluster with a GPU node pool, and the AWS resources each microservice needs (images, queues, buckets, secrets, databases). Argo CD then deploys everything *inside* the cluster.

```
Terraform (this dir)                       GitOps (gitops/, platform/)
─────────────────────                      ───────────────────────────
AWS accounts, VPC, EKS, node pools   ──▶   Argo CD, KEDA, Prometheus, vLLM, Triton, MLflow
IAM roles, SQS, S3, RDS, ECR, secrets ──▶   Deployments + ServiceAccounts that use them
           │                                          ▲
           └── SSM: /<project>/<env>/services/<svc>/config ┘
```

## Layout

```
terraform/
├── _shared/                 # versions.tf, providers.tf, common.tf — symlinked into every stack
├── modules/                 # reusable building blocks, no provider or backend config
│   ├── state-backend/       #   S3 + KMS state bucket (TLS-only, versioned, prevent_destroy)
│   ├── network/             #   VPC (wraps terraform-aws-modules/vpc) + S3/interface endpoints
│   ├── eks-cluster/         #   EKS (wraps terraform-aws-modules/eks v21) + system/cpu/gpu node groups
│   └── microservice/        #   per-service ECR, SQS+DLQ, S3, Secrets, RDS, IAM via Pod Identity
├── stacks/                  # root modules — written ONCE, deployed to every env
│   ├── network/
│   ├── eks/
│   └── services/            #   for_each over the service catalog
├── envs/                    # data only — what differs per environment
│   ├── _global/bootstrap/   #   per-account: state bucket + GitHub OIDC plan/apply roles
│   ├── dev/      {backend.hcl, common.tfvars, network.tfvars, eks.tfvars, services.tfvars}
│   ├── staging/  {…}
│   └── prod/     {…}
├── Makefile                 # make plan|apply ENV=<env> STACK=<stack>
└── .tflint.hcl
```

**Rule of thumb:** *code* lives in `modules/` and `stacks/`; *differences* live in `envs/`. Adding an environment means adding a folder of `.tfvars`, not copying `.tf` files.

## Standards

| Area | Standard |
|---|---|
| State | One state file per **(env, stack)** → `s3://<bucket>/<env>/<stack>/terraform.tfstate`. Small blast radius, fast plans. |
| Locking | S3-native `use_lockfile` (Terraform ≥ 1.10). No DynamoDB table. |
| Accounts | One AWS account per env. `allowed_account_ids` makes the provider refuse the wrong account. |
| Auth | GitHub Actions → AWS via OIDC. PRs get a read-only *plan* role; *apply* is only possible from a GitHub Environment (add required reviewers on `prod`). |
| Versions | `required_version >= 1.10`, AWS provider `~> 6.0`, community modules pinned with `~>`. Commit `.terraform.lock.hcl`. |
| Naming | `<project>-<env>[-<service>]`, e.g. `ai-platform-prod-mlflow`. Buckets add the account ID for global uniqueness. |
| Tagging | `default_tags` on the provider: Project, Environment, Stack, Owner, CostCenter, ManagedBy, Repository. Services add `Service`. |
| Secrets | Never in tfvars or state. Terraform creates Secrets Manager *containers*; RDS uses `manage_master_user_password`. |
| Inputs | Typed variables with `validation` blocks and `optional()` defaults; every variable and output documented (tflint-enforced). |
| CI | `fmt -check`, `validate`, `tflint`, `checkov` on every PR; per-env plans once OIDC roles exist. |

## Environment matrix

| | dev | staging | prod |
|---|---|---|---|
| VPC / AZs | 10.10.0.0/16 · 2 AZ | 10.20.0.0/16 · 3 AZ | 10.30.0.0/16 · 3 AZ |
| NAT | 1 shared | 1 shared | 1 per AZ |
| Interface endpoints | off (cost) | on | on |
| EKS API | public, your IP only | public, office CIDR | **private only** |
| CPU nodes | Spot, 0–4 | On-demand, 1–6 | On-demand, 3–20 |
| GPU nodes | Spot g6/g5, **0**–1 | g6, 0–2 | g6e (L40S), **1**–8 warm |
| RDS | t4g.micro, 1-day backup | t4g.medium | r7g.large, **Multi-AZ**, 14-day backup, deletion protection |
| Destroy | allowed | allowed | blocked in Makefile; prod buckets/ECR can't force-delete |

## The interesting parts

1. **Stacks talk through SSM Parameter Store, not `terraform_remote_state`.**
   `network` publishes `/<project>/<env>/network/{vpc_id,private_subnet_ids,…}`, `eks` reads them and publishes `/eks/{cluster_name,node_security_group_id}`, and `services` reads both. Consumers don't need read access to the producer's whole state file (which can contain sensitive values), and the contract is explicit and readable by anyone, including non-Terraform tools.

2. **A service catalog instead of copy-pasted services.**
   `envs/<env>/services.tfvars` is a map. Each entry turns features on (`queue`, `bucket`, `secrets`, `postgres`, `ecr`) and the `microservice` module **generates the IAM policy from exactly those features**, so a service with only a queue can't touch S3. Adding a service is a few lines of tfvars.

3. **Pod Identity everywhere, no IRSA.** Each service role trusts `pods.eks.amazonaws.com` and is bound to `<namespace>/<serviceaccount>`, with no OIDC provider per cluster and no annotations to manage in GitOps.

4. **KEDA gets least privilege, computed.** The `services` stack builds a role for `keda/keda-operator` that can call `sqs:GetQueueAttributes` only on queues whose service set `autoscale = true`. If no service opts in, the role isn't created.

5. **GPU scale-from-zero actually works.** The GPU node group is tainted `nvidia.com/gpu=true:NoSchedule` (matching `platform/vllm`). With `min_size = 0`, Cluster Autoscaler can only learn a node's shape from **ASG tags**, and EKS managed node groups don't propagate tags to their ASG. `modules/eks-cluster` adds `aws_autoscaling_group_tag` resources for the label, taint and `nvidia.com/gpu` capacity.

6. **Environment policy enforced at plan time.** Cross-variable validation (Terraform ≥ 1.9) rejects a prod plan with a non-Multi-AZ database or an unversioned bucket. `is_prod` also flips deletion protection, snapshot behaviour, secret recovery windows, `force_destroy` and `apply_immediately`.

7. **Deterministic subnet carving.** A /16 becomes /20 private subnets (VPC CNI gives pods real IPs, so they need room), /24 public and /24 intra subnets for control-plane ENIs, all computed with `cidrsubnet`, with no hand-typed CIDRs. Env CIDRs don't overlap, so Transit Gateway or peering works later.

8. **Terraform → GitOps hand-off.** `services` writes one JSON doc per service to `/<project>/<env>/services/<svc>/config` (role ARN, queue URL, bucket, DB endpoint, secret ARNs). External Secrets Operator or a Helm lookup can feed it to the manifests Argo CD deploys.

## Usage

```bash
# 0. Once per account (local state; it creates the state bucket and CI roles)
cd envs/_global/bootstrap
terraform init && terraform apply -var environment=dev -var account_id=111111111111
#    -> copy state_bucket into envs/dev/backend.hcl, role ARNs into GitHub repo variables

# 1. Everything for an environment, in dependency order
cd ../../..
make plan-all  ENV=dev
make apply-all ENV=dev

# 2. Day-to-day: one stack at a time
make plan  ENV=dev STACK=services
make apply ENV=dev STACK=services

# prod needs an explicit confirmation
make plan  ENV=prod STACK=eks
make apply ENV=prod STACK=eks CONFIRM=prod

# 3. Talk to the cluster, then hand off to GitOps
aws eks update-kubeconfig --region us-west-2 --name ai-platform-dev
cd .. && make bootstrap     # repo root: installs Argo CD + app-of-apps
```

Before a real apply, replace the placeholder account IDs (`111111111111` …) and the `203.0.113.x` CIDRs in `envs/`.

## Cost warning

Even dev isn't free: EKS control plane (~$73/mo), NAT gateway, 2 system nodes and RDS add up to roughly **$200+/mo** before any GPU hours. `make destroy ENV=dev STACK=…` in reverse order (`services` → `eks` → `network`) when you're done.
