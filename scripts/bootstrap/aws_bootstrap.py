#!/usr/bin/env python3
"""Bootstrap one AWS account/environment end to end, idempotently.

    python3 scripts/bootstrap/aws_bootstrap.py --env dev --account-id 123456789012 --region us-west-2
    ... --dry-run          # print every action, change nothing
    ... --apply            # afterwards run network -> eks -> services for this env

Steps (each safe to re-run):
  1. preflight   - tools present; `aws sts get-caller-identity` is the account you named (refuses otherwise)
  2. bootstrap   - terraform/envs/_global/bootstrap: state bucket + KMS + GitHub OIDC plan/apply roles.
                   First run uses LOCAL state (the bucket doesn't exist yet) ...
  3. migrate     - ... then moves that state INTO the bucket it just created (no tfstate left on your laptop)
  4. configure   - writes the real bucket/account/region into terraform/envs/<env>/{backend.hcl,*.tfvars}
  5. github      - sets repo variables AWS_PLAN_ROLE_ARN_<ENV>, AWS_APPLY_ROLE_ARN_<ENV>, AWS_REGION, TF_PLAN_ENABLED
  6. apply       - optional: make -C terraform apply-all ENV=<env> (prod requires --i-mean-prod)

No credentials are written anywhere: the AWS CLI / Terraform use your existing profile or SSO session.
`--endpoint` points everything at a fake AWS (moto) for CI tests of this script.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TF = ROOT / "terraform"
BOOT = TF / "envs" / "_global" / "bootstrap"
PROJECT = "ai-platform"
PLACEHOLDER_ACCOUNTS = {"dev": "111111111111", "staging": "222222222222", "prod": "333333333333"}
PLACEHOLDER_REGION = "us-west-2"
STATE_KEY = "_global/bootstrap/{env}/terraform.tfstate"


class BootstrapError(SystemExit):
    pass


def bucket_name(account_id: str, region: str) -> str:
    """Must match modules/state-backend: <project>-tfstate-<account>-<region>."""
    return f"{PROJECT}-tfstate-{account_id}-{region}"


# ---------------------------------------------------------------- file edits (pure, unit-tested)
def configure_env_text(text: str, env: str, account_id: str, region: str) -> str:
    """Replace the env's placeholder account id and region in a backend.hcl / *.tfvars file."""
    text = text.replace(PLACEHOLDER_ACCOUNTS[env], account_id)
    text = re.sub(r'(?m)^(\s*region\s*=\s*")[^"]*(")', rf"\g<1>{region}\g<2>", text)
    text = re.sub(r'(?m)^(\s*bucket\s*=\s*")[^"]*(")', rf"\g<1>{bucket_name(account_id, region)}\g<2>", text)
    return text


def configure_env_files(env: str, account_id: str, region: str, dry_run: bool) -> list[Path]:
    changed = []
    for f in sorted((TF / "envs" / env).glob("*")):
        if f.suffix not in {".hcl", ".tfvars"}:
            continue
        new = configure_env_text(f.read_text(), env, account_id, region)
        if new != f.read_text():
            changed.append(f)
            if not dry_run:
                f.write_text(new)
    return changed


def local_backend_override(env: str) -> str:
    return f'terraform {{\n  backend "local" {{\n    path = "state/{env}.tfstate"\n  }}\n}}\n'


def s3_backend_override() -> str:
    return 'terraform {\n  backend "s3" {}\n}\n'


def provider_override(endpoint: str) -> str:
    """Point the AWS provider at a fake endpoint (moto) - CI only."""
    # s3control: the AWS provider reads bucket tags via S3 Control, which prefixes the host with the
    # account id (<account>.<endpoint host>) - so the fake endpoint must be a resolvable *name*, e.g. localhost.
    services = ["s3", "s3control", "kms", "iam", "sts"]
    eps = "\n".join(f'      {s} = "{endpoint}"' for s in services)
    return (
        'provider "aws" {\n'
        "  s3_use_path_style           = true\n"
        "  skip_credentials_validation = true\n"
        "  skip_requesting_account_id  = false\n"
        "  skip_metadata_api_check     = true\n"
        "  endpoints {\n" + eps + "\n  }\n}\n"
    )


def backend_config(env: str, account_id: str, region: str, endpoint: str | None) -> list[str]:
    cfg = [f"bucket={bucket_name(account_id, region)}", f"key={STATE_KEY.format(env=env)}", f"region={region}",
           "encrypt=true"]
    if endpoint:
        cfg += [f'endpoints={{s3="{endpoint}"}}', "use_path_style=true", "skip_credentials_validation=true",
                "skip_requesting_account_id=true", "skip_metadata_api_check=true", "skip_region_validation=true"]
    else:
        cfg.append("use_lockfile=true")
    return [f"-backend-config={c}" for c in cfg]


# ---------------------------------------------------------------- runner
class Runner:
    def __init__(self, dry_run: bool, endpoint: str | None):
        self.dry_run, self.endpoint = dry_run, endpoint

    def run(self, cmd: list[str], cwd: Path = ROOT, capture: bool = False, mutating: bool = True,
            env: dict | None = None) -> str:
        shown = " ".join(cmd)
        if self.dry_run and mutating:
            print(f"[dry-run] {shown}")
            return ""
        print(f"$ {shown}", flush=True)
        proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=capture,  # noqa: S603
                              env={**os.environ, **(env or {})})
        if proc.returncode != 0:
            raise BootstrapError(f"command failed ({proc.returncode}): {shown}\n{(proc.stderr or '')[-2000:]}")
        return proc.stdout if capture else ""

    def aws(self, *args: str) -> str:
        ep = ["--endpoint-url", self.endpoint] if self.endpoint else []
        return self.run(["aws", *ep, *args, "--output", "json"], capture=True, mutating=False)

    def write(self, path: Path, content: str) -> None:
        if self.dry_run:
            print(f"[dry-run] write {path.relative_to(ROOT)}")
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def state_in_bucket(r: Runner, env: str, account_id: str, region: str) -> bool:
    try:
        r.aws("s3api", "head-object", "--bucket", bucket_name(account_id, region), "--key", STATE_KEY.format(env=env))
        return True
    except BootstrapError:
        return False


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--env", required=True, choices=sorted(PLACEHOLDER_ACCOUNTS))
    p.add_argument("--account-id", required=True)
    p.add_argument("--region", default=PLACEHOLDER_REGION)
    p.add_argument("--github-repo", default="SunnGHubX/sunn-platform-lab")
    p.add_argument("--skip-github", action="store_true", help="don't set GitHub repo variables")
    p.add_argument("--apply", action="store_true", help="also apply network -> eks -> services for this env")
    p.add_argument("--i-mean-prod", action="store_true", help="required with --apply for prod")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--endpoint", help="fake AWS endpoint (moto) for CI tests of this script")
    a = p.parse_args(argv)

    if not re.fullmatch(r"\d{12}", a.account_id):
        raise BootstrapError("--account-id must be 12 digits")
    if a.apply and a.env == "prod" and not a.i_mean_prod:
        raise BootstrapError("refusing to apply prod without --i-mean-prod")
    r = Runner(a.dry_run, a.endpoint)
    tf_env = {"TF_IN_AUTOMATION": "1", "TF_DATA_DIR": str(BOOT / ".terraform" / a.env)}

    # 1. preflight
    print(f"== preflight ({a.env} / {a.account_id} / {a.region})")
    needed = ["terraform", "aws"] + ([] if a.skip_github else ["gh"])
    missing = [t for t in needed if not shutil.which(t)]
    if missing:
        raise BootstrapError(f"missing tools: {', '.join(missing)}. Run `make prereqs-install PROFILE=all`.")
    ident = json.loads(r.aws("sts", "get-caller-identity") or "{}")
    if ident.get("Account") != a.account_id:
        raise BootstrapError(f"your credentials are for account {ident.get('Account')!r}, not {a.account_id}. "
                             "Switch profile (AWS_PROFILE / aws sso login) and re-run.")
    print(f"   caller: {ident.get('Arn')}")

    if a.endpoint:  # gitignored, like backend_override.tf
        r.write(BOOT / "provider_override.tf", provider_override(a.endpoint))
    tf_vars = [f"-var=environment={a.env}", f"-var=account_id={a.account_id}", f"-var=region={a.region}",
               f"-var=github_repository={a.github_repo}"]
    bootstrap_dir = ["-chdir=" + str(BOOT)]

    # 2 + 3. bootstrap, with state migration on first run
    if state_in_bucket(r, a.env, a.account_id, a.region):
        print("== bootstrap state already in S3: re-applying from there (idempotent)")
        r.write(BOOT / "backend_override.tf", s3_backend_override())
        r.run(["terraform", *bootstrap_dir, "init", "-input=false", "-reconfigure",
               *backend_config(a.env, a.account_id, a.region, a.endpoint)], env=tf_env)
        r.run(["terraform", *bootstrap_dir, "apply", "-input=false", "-auto-approve", *tf_vars], env=tf_env)
    else:
        print("== first run: bootstrap with local state")
        r.write(BOOT / "backend_override.tf", local_backend_override(a.env))
        r.run(["terraform", *bootstrap_dir, "init", "-input=false", "-reconfigure"], env=tf_env)
        r.run(["terraform", *bootstrap_dir, "apply", "-input=false", "-auto-approve", *tf_vars], env=tf_env)
        print("== migrating bootstrap state into the bucket it created")
        r.write(BOOT / "backend_override.tf", s3_backend_override())
        r.run(["terraform", *bootstrap_dir, "init", "-input=false", "-migrate-state", "-force-copy",
               *backend_config(a.env, a.account_id, a.region, a.endpoint)], env=tf_env)
        local_state = BOOT / "state" / f"{a.env}.tfstate"
        if not a.dry_run and state_in_bucket(r, a.env, a.account_id, a.region) and local_state.exists():
            local_state.unlink()
            for backup in local_state.parent.glob(f"{a.env}.tfstate*"):
                backup.unlink()
            print(f"   removed local {local_state.relative_to(ROOT)} (state now lives in S3)")

    outputs = {}
    if not a.dry_run:
        outputs = json.loads(r.run(["terraform", *bootstrap_dir, "output", "-json"], capture=True,
                                   mutating=False, env=tf_env))

    # 4. configure env files
    print(f"== configuring terraform/envs/{a.env}")
    for f in configure_env_files(a.env, a.account_id, a.region, a.dry_run):
        print(f"   updated {f.relative_to(ROOT)}")

    # 5. GitHub repo variables for the OIDC plan workflow
    if not a.skip_github and outputs:
        print("== GitHub repo variables")
        env_u = a.env.upper()
        for name, value in [(f"AWS_PLAN_ROLE_ARN_{env_u}", outputs["plan_role_arn"]["value"]),
                            (f"AWS_APPLY_ROLE_ARN_{env_u}", outputs["apply_role_arn"]["value"]),
                            ("AWS_REGION", a.region), ("TF_PLAN_ENABLED", "true")]:
            r.run(["gh", "variable", "set", name, "--repo", a.github_repo, "--body", value])

    # 6. optional apply of the env's stacks
    if a.apply:
        confirm = ["CONFIRM=prod"] if a.env == "prod" else []
        r.run(["make", "-C", "terraform", "apply-all", f"ENV={a.env}", *confirm])

    print(f"\n✅ {a.env} bootstrapped. State bucket: {bucket_name(a.account_id, a.region)}")
    print("Next: review & commit terraform/envs/" + a.env + ", then `make -C terraform plan-all ENV=" + a.env + "`")
    return 0


if __name__ == "__main__":
    sys.exit(main())
