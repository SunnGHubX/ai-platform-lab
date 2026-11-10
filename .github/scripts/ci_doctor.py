#!/usr/bin/env python3
"""ci-doctor: explain why a GitHub Actions run failed and what to do next.

Reads the failed jobs' logs of a workflow run, classifies each failure with regex rules
(transient vs. real, which tool, which test), and writes a markdown diagnosis to the job
summary and (optionally) as a single, updated PR comment.

    GH_TOKEN=... python3 .github/scripts/ci_doctor.py --repo owner/repo --run-id 123 [--pr 7]
    python3 .github/scripts/ci_doctor.py --log-file failed.log          # classify a local log
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field

MARKER = "<!-- ci-doctor -->"
ANSI = re.compile(r"\x1b\[[0-9;]*m")
GH_PREFIX = re.compile(r"^[^\t]*\t[^\t]*\t\S+Z ")  # "job\tstep\t<timestamp> " from `gh run view --log-failed`
TS_PREFIX = re.compile(r"^\ufeff?\d{4}-\d\d-\d\dT[\d:.]+Z ")    # "<timestamp> " from the jobs/{id}/logs API


@dataclass(frozen=True)
class Rule:
    id: str
    title: str
    pattern: str
    advice: str
    transient: bool = False
    capture: str | None = None  # regex group 1 = the specific failing item to list


RULES: list[Rule] = [
    # ---- transient: re-run first
    Rule("rate-limit", "Rate limited by a registry or API", r"HTTP 429|Too Many Requests|toomanyrequests|rate limit exceeded",
         "Transient. Re-run failed jobs; if it repeats, add registry auth or caching.", transient=True),
    Rule("network-flake", "Network flake", r"Connection reset by peer|ECONNRESET|TLS handshake timeout|"
         r"Temporary failure in name resolution|i/o timeout|lost connection to pod|CONNECT tunnel failed",
         "Usually transient. Re-run; if it persists, check the service's status page.", transient=True),
    Rule("runner-timeout", "Job hit its time limit", r"has exceeded the maximum execution time|The operation was canceled",
         "Look at the last step before cancellation; a hang usually means a rollout or port-forward never became ready.",
         transient=True),
    # ---- real failures, most specific first
    Rule("terraform-fmt", "Terraform formatting", r"Terraform exited with code 3|^--- old/",
         "Run `make -C terraform fmt` and commit."),
    Rule("terraform-test", "Terraform test failed", r'run "([^"]+)"\.\.\. fail',
         "Run `make -C terraform test` locally; read the assertion's error_message.", capture=r'run "([^"]+)"\.\.\. fail'),
    Rule("terraform-validate", "Terraform error", r"^│ Error: (.+)",
         "Read the boxed error: resource, file and line are right below it.", capture=r"^│ Error: (.+)"),
    Rule("pytest", "Python tests failed", r"^FAILED (\S+)", "Run the failing tests with `pytest -k <name> -vv`.",
         capture=r"^FAILED (\S+)"),
    Rule("rego-test", "Rego unit test failed", r"data\.\S+: FAIL", "Run `make test-policy` and check the fixture.",
         capture=r"(data\.\S+): FAIL"),
    Rule("policy-violation", "Policy violation in rendered manifests", r"^FAIL - ",
         "A manifest breaks a rule in policy/kubernetes. Fix the manifest (or the rule, with a test).",
         capture=r"^FAIL - (.+)"),
    Rule("promtool", "SLO alert unit test failed", r"alertname: (\S+)|FAILED:\s*$",
         "Run `make test-slo`; compare exp_labels/exp_annotations with the rule.", capture=r"alertname: (\S+)"),
    Rule("generated-drift", "Generated files are stale", r"run 'python3 sre/slo/build.py'",
         "Run `python3 sre/slo/build.py` and commit platform/slo."),
    Rule("yamllint", "YAML lint", r"^\s*\d+:\d+\s+error\s+(.+)", "Run `yamllint .`.", capture=r"^\s*\d+:\d+\s+error\s+(.+)"),
    Rule("ruff", "Python lint (ruff)", r"^(\S+\.py:\d+:\d+: [A-Z]+\d+ .+)", "Run `ruff check --fix`.",
         capture=r"^(\S+\.py:\d+:\d+: [A-Z]+\d+ .+)"),
    Rule("kubeconform", "Kubernetes schema validation", r"is invalid:|failed validation", "Fix the manifest field named in the error."),
    Rule("gitleaks", "Secret detected", r"leaks found|Finding:\s", "Remove the secret, **rotate it**, then rewrite history if needed."),
    Rule("trivy", "Vulnerable image or dependency", r"Total: \d+ \(.*CRITICAL: [1-9]",
         "Bump the base image / package to the fixed version Trivy lists."),
    Rule("oom", "Pod OOMKilled in e2e", r"OOMKilled", "Raise the memory limit or reduce workers; see docs/troubleshooting.md#oomkilled."),
    Rule("devcontainer-feature", "Devcontainer feature failed to install", r'ERROR: Feature "([^"]+)"',
         "Read the feature's '(!)' lines just above; usually an option unsupported on the base image's distro.",
         capture=r'ERROR: Feature "([^"]+)"'),
    Rule("docker-build", "Docker build failed", r"failed to solve", "Reproduce with `docker build` locally."),
    Rule("exercise", "Exercise acceptance checks not met", r"^❌ (.+)", "Run `make exercise EX=NN` locally.",
         capture=r"^❌ (.+)"),
    Rule("shellcheck", "Shell lint (shellcheck)", r"\^-- SC\d{4}", "Run `shellcheck <file>` and follow the wiki link for the code.",
         capture=r"\^-- (SC\d{4} \(\w+\): .+)"),
    Rule("ansible-lint", "ansible-lint", r"Rule Violation Summary|^\S+\.ya?ml:\d+:\d+: \S+\[",
         "Run `cd ansible && ansible-lint`."),
]


@dataclass
class Diagnosis:
    job: str
    matches: list[tuple[Rule, list[str]]] = field(default_factory=list)
    tail: list[str] = field(default_factory=list)

    @property
    def transient_only(self) -> bool:
        return bool(self.matches) and all(r.transient for r, _ in self.matches)


def clean(lines: list[str]) -> list[str]:
    return [TS_PREFIX.sub("", GH_PREFIX.sub("", ANSI.sub("", ln))).rstrip() for ln in lines]


def classify(job: str, log: str) -> Diagnosis:
    lines = clean(log.splitlines())
    text = "\n".join(lines)
    # Context = the lines leading up to the first ##[error], not the post-job cleanup noise at the end.
    first_err = next((i for i, ln in enumerate(lines) if "##[error]" in ln), len(lines) - 1)
    d = Diagnosis(job=job, tail=[ln for ln in lines[max(0, first_err - 20):first_err + 1] if ln.strip()][-15:])
    for rule in RULES:
        if not re.search(rule.pattern, text, re.MULTILINE):
            continue
        items: list[str] = []
        if rule.capture:
            items = list(dict.fromkeys(m.group(1).strip() for m in re.finditer(rule.capture, text, re.MULTILINE)))[:8]
        d.matches.append((rule, items))
    # A real failure explains the run; drop transient noise that merely co-occurs with it.
    if any(not r.transient for r, _ in d.matches):
        d.matches = [(r, i) for r, i in d.matches if not r.transient]
    return d


def render(run_name: str, run_url: str, diagnoses: list[Diagnosis]) -> str:
    out = [MARKER, f"### 🩺 CI doctor: `{run_name}` failed", "", f"[Open the run]({run_url})", ""]
    if diagnoses and all(d.transient_only for d in diagnoses):
        out += ["> **Looks transient.** Re-run failed jobs before debugging.", ""]
    for d in diagnoses:
        out.append(f"#### Job `{d.job}`")
        if not d.matches:
            out += ["No known pattern matched. Last log lines:", "```", *d.tail, "```"]
        for rule, items in d.matches:
            badge = "🔁 transient" if rule.transient else "🔴"
            out.append(f"- {badge} **{rule.title}**: {rule.advice}")
            out += [f"  - `{i[:180]}`" for i in items]
        out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------- GitHub I/O (gh CLI)
def gh(*args: str, input_: str | None = None) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True, input=input_).stdout  # noqa: S603, S607


def failed_jobs(repo: str, run_id: str) -> list[dict]:
    jobs = json.loads(gh("api", f"repos/{repo}/actions/runs/{run_id}/jobs?per_page=100"))["jobs"]
    return [j for j in jobs if j.get("conclusion") in {"failure", "timed_out"}]


def job_log(repo: str, job_id: int) -> str:
    try:
        return gh("api", f"repos/{repo}/actions/jobs/{job_id}/logs")
    except subprocess.CalledProcessError as e:
        return e.stderr or ""


def upsert_comment(repo: str, pr: int, body: str) -> None:
    comments = json.loads(gh("api", f"repos/{repo}/issues/{pr}/comments?per_page=100"))
    mine = next((c for c in comments if MARKER in (c.get("body") or "")), None)
    payload = json.dumps({"body": body[:60000]})
    if mine:
        gh("api", "-X", "PATCH", f"repos/{repo}/issues/comments/{mine['id']}", "--input", "-", input_=payload)
    else:
        gh("api", "-X", "POST", f"repos/{repo}/issues/{pr}/comments", "--input", "-", input_=payload)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--repo")
    p.add_argument("--run-id")
    p.add_argument("--pr", type=int, action="append", default=[])
    p.add_argument("--log-file", help="classify a local log file instead of calling GitHub")
    a = p.parse_args(argv)

    if a.log_file:
        md = render("local", "#", [classify(a.log_file, open(a.log_file, encoding="utf-8", errors="ignore").read())])
    else:
        run = json.loads(gh("api", f"repos/{a.repo}/actions/runs/{a.run_id}"))
        diags = [classify(j["name"], job_log(a.repo, j["id"])) for j in failed_jobs(a.repo, a.run_id)]
        md = render(run["name"], run["html_url"], diags)
        for pr in a.pr:
            upsert_comment(a.repo, pr, md)
    print(md)
    if summary := os.getenv("GITHUB_STEP_SUMMARY"):
        with open(summary, "a") as fh:
            fh.write(md + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
