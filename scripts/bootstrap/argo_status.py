#!/usr/bin/env python3
"""Read `kubectl get applications -o json` on stdin; print '<total> <not-ready...>' and exit 0 when all are
Synced + Healthy (and at least `--min` exist), else exit 1."""
import argparse
import json
import sys


def not_ready(apps: list[dict]) -> list[str]:
    out = []
    for a in apps:
        st = a.get("status", {})
        sync, health = st.get("sync", {}).get("status", "?"), st.get("health", {}).get("status", "?")
        if sync != "Synced" or health != "Healthy":
            out.append(f"{a['metadata']['name']}={sync}/{health}")
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--min", type=int, default=2)
    a = p.parse_args()
    apps = json.load(sys.stdin).get("items", [])
    bad = not_ready(apps)
    print(" ".join(bad) if bad else f"all {len(apps)} applications Synced/Healthy")
    return 0 if apps and len(apps) >= a.min and not bad else 1


if __name__ == "__main__":
    sys.exit(main())
