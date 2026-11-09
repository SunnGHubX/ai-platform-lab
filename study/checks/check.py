#!/usr/bin/env python3
"""Exercise checker: turns each exercise's acceptance criteria into automated checks.

    python3 study/checks/check.py 01            # check one exercise
    python3 study/checks/check.py --all --quick # status board (static checks only)
    python3 study/checks/check.py 06 --strict   # CI mode: missing tools = failure, not skip

Check types (see exercises.yaml):
    file      - path (or glob) exists
    grep      - regex found in file(s) at least `min` times
    absent    - regex must NOT be found (e.g. "the workaround was removed")
    run       - shell command exits 0 (skipped with --quick, or if `needs` tools are missing)
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SPEC = Path(__file__).with_name("exercises.yaml")

PASS, FAIL, SKIP = "pass", "fail", "skip"
ICON = {PASS: "✅", FAIL: "❌", SKIP: "⏭️"}


@dataclass
class Result:
    name: str
    status: str
    detail: str = ""


def _files(pattern: str, root: Path) -> list[Path]:
    return sorted(Path(p) for p in glob.glob(str(root / pattern), recursive=True) if Path(p).is_file())


def run_check(check: dict, root: Path = ROOT, quick: bool = False, strict: bool = False) -> Result:
    name = check["name"]
    kind = next(k for k in ("file", "grep", "absent", "run") if k in check)

    if kind == "file":
        found = glob.glob(str(root / check["file"]), recursive=True)
        return Result(name, PASS if found else FAIL, "" if found else f"missing: {check['file']}")

    if kind in ("grep", "absent"):
        spec = check[kind]
        files = _files(spec["path"], root)
        if not files:
            return Result(name, FAIL, f"no file matches {spec['path']}")
        rx = re.compile(spec["pattern"], re.MULTILINE)
        hits = sum(len(rx.findall(f.read_text(errors="ignore"))) for f in files)
        if kind == "absent":
            return Result(name, PASS if hits == 0 else FAIL, f"{hits} unexpected match(es)" if hits else "")
        need = spec.get("min", 1)
        return Result(name, PASS if hits >= need else FAIL, "" if hits >= need else f"found {hits}, need {need}")

    # run
    if quick:
        return Result(name, SKIP, "--quick")
    missing = [t for t in check.get("needs", []) if shutil.which(t) is None]
    if missing:
        return Result(name, FAIL if strict else SKIP, f"tool(s) not installed: {', '.join(missing)}")
    proc = subprocess.run(check["run"], shell=True, cwd=root, capture_output=True, text=True,  # noqa: S602
                          timeout=check.get("timeout", 900))
    tail = (proc.stdout + proc.stderr).strip().splitlines()[-15:]
    return Result(name, PASS if proc.returncode == 0 else FAIL, "" if proc.returncode == 0 else "\n".join(tail))


def load_spec(path: Path = SPEC) -> dict:
    """Exercise ids only (top-level keys like x-commands are YAML anchors, not exercises)."""
    return {k: v for k, v in yaml.safe_load(path.read_text()).items() if k.isdigit()}


def check_exercise(ex_id: str, spec: dict, **kw) -> list[Result]:
    return [run_check(c, **kw) for c in spec[ex_id]["checks"]]


def summarize(ex_id: str, title: str, results: list[Result]) -> str:
    lines = [f"### Exercise {ex_id}: {title}", "", "| | Check | Detail |", "|---|---|---|"]
    for r in results:
        detail = r.detail.replace("\n", "<br>").replace("|", "\\|")[:600]
        lines.append(f"| {ICON[r.status]} | {r.name} | {detail} |")
    passed = sum(r.status == PASS for r in results)
    lines += ["", f"**{passed}/{len(results)} checks passed**", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("exercise", nargs="?", help="exercise id, e.g. 01 (or a branch name like ex/01-redis)")
    p.add_argument("--all", action="store_true", help="status board for every exercise")
    p.add_argument("--quick", action="store_true", help="static checks only (no `run` checks)")
    p.add_argument("--strict", action="store_true", help="missing tools fail instead of skip (CI)")
    a = p.parse_args(argv)

    spec = load_spec()
    if a.all:
        ids = sorted(spec)
    elif a.exercise:
        m = re.search(r"(\d{2})", a.exercise)
        if not m or m.group(1) not in spec:
            print(f"unknown exercise {a.exercise!r}; known: {', '.join(sorted(spec))}", file=sys.stderr)
            return 2
        ids = [m.group(1)]
    else:
        p.error("give an exercise id or --all")

    failed = False
    report = []
    for ex_id in ids:
        results = check_exercise(ex_id, spec, quick=a.quick, strict=a.strict)
        failed |= any(r.status == FAIL for r in results)
        report.append(summarize(ex_id, spec[ex_id]["title"], results))
        if a.all:
            done = all(r.status != FAIL for r in results)
            print(f"{'✅' if done else '⬜'} {ex_id}  {spec[ex_id]['title']}  "
                  f"({sum(r.status == PASS for r in results)}/{len(results)})")
        else:
            for r in results:
                print(f"{ICON[r.status]} {r.name}" + (f"\n    {r.detail}" if r.detail and r.status != PASS else ""))

    if summary := os.getenv("GITHUB_STEP_SUMMARY"):
        with open(summary, "a") as fh:
            fh.write("\n".join(report))
    return 1 if failed and not a.all else 0


if __name__ == "__main__":
    sys.exit(main())
