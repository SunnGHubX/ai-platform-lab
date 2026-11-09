#!/usr/bin/env python3
"""Report how far pinned versions (Helm charts in gitops/, images in platform/) are behind upstream.
Never fails the build: drift is information for a planned upgrade, not an outage."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SEMVER = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def parse(v: str) -> tuple[int, int, int] | None:
    m = SEMVER.match(v.strip())
    return tuple(int(x) for x in m.groups()) if m else None  # type: ignore[return-value]


def status(pinned: str, latest: str | None) -> str:
    p, l_ = parse(pinned), parse(latest or "")
    if not p or not l_:
        return "❔ unknown"
    if p >= l_:
        return "✅ current"
    if p[0] < l_[0]:
        return "⚠️ major behind"
    if p[1] < l_[1]:
        return "⬆️ minor behind"
    return "🩹 patch behind"


def latest_stable(versions: list[str]) -> str | None:
    stable = [v for v in versions if parse(v)]
    return max(stable, key=parse) if stable else None  # type: ignore[arg-type]


def helm_latest(repo_url: str, chart: str) -> str | None:
    with urllib.request.urlopen(f"{repo_url.rstrip('/')}/index.yaml", timeout=60) as r:  # noqa: S310 - public chart repos
        index = yaml.safe_load(r)
    return latest_stable([e["version"] for e in index.get("entries", {}).get(chart, [])])


def pypi_latest(pkg: str) -> str | None:
    out = subprocess.run([sys.executable, "-m", "pip", "index", "versions", pkg],  # noqa: S603
                         capture_output=True, text=True, timeout=60).stdout
    m = re.search(rf"^{re.escape(pkg)} \(([^)]+)\)", out, re.MULTILINE)
    return m.group(1) if m else None


def charts() -> list[dict]:
    rows = []
    for f in sorted((ROOT / "gitops").rglob("*.yaml")):
        app = yaml.safe_load(f.read_text())
        if not isinstance(app, dict) or app.get("kind") != "Application":
            continue
        for src in app["spec"].get("sources") or [app["spec"].get("source", {})]:
            if "chart" in src:
                rows.append({"name": src["chart"], "kind": "helm", "pinned": src["targetRevision"],
                             "repo": src["repoURL"], "where": str(f.relative_to(ROOT))})
    return rows


def images() -> list[dict]:
    """Images whose upstream release stream is on PyPI (same version numbers as the image tags)."""
    rows = []
    for name, path, pkg in [("mlflow", "platform/mlflow/deployment.yaml", "mlflow"),
                            ("vllm", "platform/vllm/deployment.yaml", "vllm")]:
        m = re.search(r"image:\s*\S+:v?([\d.]+)", (ROOT / path).read_text())
        if m:
            rows.append({"name": name, "kind": "image", "pinned": m.group(1), "pkg": pkg, "where": path})
    return rows


def main() -> int:
    lines = ["### Version drift", "", "| Component | Type | Pinned | Latest | Status | Where |", "|---|---|---|---|---|---|"]
    for row in charts() + images():
        try:
            latest = helm_latest(row["repo"], row["name"]) if row["kind"] == "helm" else pypi_latest(row["pkg"])
        except Exception as e:  # noqa: BLE001 - one unreachable repo shouldn't hide the rest
            latest = f"error: {type(e).__name__}"
        lines.append(f"| {row['name']} | {row['kind']} | {row['pinned']} | {latest} | "
                     f"{status(row['pinned'], latest if latest and not latest.startswith('error') else None)} | `{row['where']}` |")
    md = "\n".join(lines) + "\n"
    print(md)
    if s := os.getenv("GITHUB_STEP_SUMMARY"):
        with open(s, "a") as fh:
            fh.write(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
