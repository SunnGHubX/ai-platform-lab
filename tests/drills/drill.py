#!/usr/bin/env python3
"""Run one break-fix drill against a running e2e cluster (see scenarios.yaml and run_drill.sh)."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "triage"))
import triage  # noqa: E402

SCENARIOS = yaml.safe_load((Path(__file__).with_name("scenarios.yaml")).read_text())
DEFAULT_FIX = ["kubectl apply -k tests/e2e/kustomize/inference",
               "kubectl -n inference rollout status deploy/inference-gateway --timeout=180s",
               "kubectl -n inference rollout status deploy/vllm --timeout=180s"]


def sh(cmd: str) -> None:
    print(f"$ {cmd}", flush=True)
    subprocess.run(cmd, shell=True, check=True, cwd=ROOT)  # noqa: S602 - commands come from our own scenarios.yaml


def chat(gateway: str, key: str, model: str = "mock") -> int:
    req = urllib.request.Request(f"{gateway}/v1/chat/completions", method="POST",
                                 data=json.dumps({"model": model, "messages": [{"role": "user", "content": "x"}]}).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:  # noqa: S310 - localhost port-forward
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:  # noqa: BLE001
        return 0


def failing_load(gateway: str, key: str, stop: threading.Event) -> None:
    while not stop.is_set():
        chat(gateway, key, model="fail")
        time.sleep(0.2)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("scenario", choices=sorted(SCENARIOS))
    p.add_argument("--bundle", type=Path, default=Path("/tmp/drill-bundle"))
    p.add_argument("--prom-url", default="http://127.0.0.1:19090")
    p.add_argument("--gateway-url", default="http://127.0.0.1:18080")
    p.add_argument("--api-key", default="e2e-test-key")
    p.add_argument("--no-reveal", action="store_true", help="practice mode: don't print root cause / lesson")
    a = p.parse_args()
    sc = SCENARIOS[a.scenario]
    summary = Path(os.environ.get("GITHUB_STEP_SUMMARY", "/dev/null"))

    def out(md: str) -> None:
        print(md, flush=True)
        with summary.open("a") as fh:
            fh.write(md + "\n")

    out(f"## Drill `{a.scenario}`: {sc['title']}\n\n**Symptom:** {sc['symptom']}\n")

    # 1. break
    for cmd in sc.get("break", []):
        sh(cmd)
    stop = threading.Event()
    if sc.get("load") == "fail":
        threading.Thread(target=failing_load, args=(a.gateway_url, a.api_key, stop), daemon=True).start()

    # 2. detect: poll triage until every expected finding shows up
    expected = set(sc["expect"])
    deadline = time.time() + sc.get("timeout", 240)
    findings: list = []
    while time.time() < deadline:
        state = triage.collect(a.bundle, a.prom_url)  # alerts are cheap; always include them
        findings = triage.analyze(state)
        if expected <= {f.id for f in findings}:
            break
        time.sleep(10)
    stop.set()
    triage.collect_details(a.bundle, findings)
    (a.bundle / "report.md").write_text(triage.report(findings))
    detected = expected <= {f.id for f in findings}
    out(triage.report(findings))
    out(f"**Detection:** {'✅' if detected else '❌'} expected `{', '.join(sorted(expected))}`\n")
    if not a.no_reveal:
        out(f"<details><summary>Root cause &amp; lesson</summary>\n\n**Root cause:** {sc['root_cause']}\n\n"
            f"**Lesson:** {sc['lesson']}\n</details>\n")

    # 3. fix + verify recovery
    for cmd in sc.get("fix", DEFAULT_FIX):
        sh(cmd)
    recovered = True
    if sc.get("verify", True):
        deadline = time.time() + 180
        while time.time() < deadline and chat(a.gateway_url, a.api_key) != 200:
            time.sleep(5)
        recovered = chat(a.gateway_url, a.api_key) == 200
        out(f"**Recovery after fix:** {'✅ gateway serving 200 again' if recovered else '❌ still failing'}\n")

    return 0 if detected and recovered else 1


if __name__ == "__main__":
    sys.exit(main())
