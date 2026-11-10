#!/usr/bin/env python3
"""Check (and optionally install) everything this repo needs, at the versions pinned in mise.toml.

    python3 scripts/bootstrap/prereqs.py                  # check the "lab" profile
    python3 scripts/bootstrap/prereqs.py --install        # install missing/wrong tools into ./.bin (checksum-verified)
    python3 scripts/bootstrap/prereqs.py --profile all    # lab + iac + aws

Profiles
    lab  : docker (running, enough memory), kind, kubectl, helm, free ports   -> `make up`
    iac  : terraform, tflint                                                  -> `make -C terraform test`
    aws  : aws CLI, gh CLI                                                    -> `make aws-bootstrap`
Tools go into ./.bin (gitignored); the Makefile puts it first on PATH. Nothing is installed system-wide,
nothing is piped into a shell, and every download is verified against the publisher's checksum file.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import platform
import re
import shutil
import socket
import stat
import subprocess
import sys
import tarfile
import tomllib
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / ".bin"
MIN_DOCKER_MEM_GB = 6
LAB_PORTS = [8080, 3000, 5000]

PROFILES = {
    "lab": ["docker", "kind", "kubectl", "helm"],
    "iac": ["terraform", "tflint"],
    "aws": ["aws", "gh"],
}
PROFILES["all"] = PROFILES["lab"] + PROFILES["iac"] + PROFILES["aws"]

# How to read each tool's version from its CLI
VERSION_CMD = {
    "kind": ["kind", "version"],
    "kubectl": ["kubectl", "version", "--client"],
    "helm": ["helm", "version", "--short"],
    "terraform": ["terraform", "version"],
    "tflint": ["tflint", "--version"],
    "docker": ["docker", "--version"],
    "aws": ["aws", "--version"],
    "gh": ["gh", "--version"],
}
# Tools we only check (installing them is the OS package manager's job)
CHECK_ONLY = {"docker": "https://docs.docker.com/get-docker/", "aws": "https://aws.amazon.com/cli/",
              "gh": "https://cli.github.com/"}


@dataclass
class Result:
    tool: str
    ok: bool
    have: str | None
    want: str | None
    note: str = ""


def pinned_versions(path: Path = ROOT / "mise.toml") -> dict[str, str]:
    return {k: str(v) for k, v in tomllib.loads(path.read_text())["tools"].items()}


def platform_id() -> tuple[str, str]:
    os_ = {"Linux": "linux", "Darwin": "darwin"}.get(platform.system())
    arch = {"x86_64": "amd64", "amd64": "amd64", "arm64": "arm64", "aarch64": "arm64"}.get(platform.machine().lower())
    if not os_ or not arch:
        raise SystemExit(f"unsupported platform {platform.system()}/{platform.machine()} (use the devcontainer)")
    return os_, arch


def parse_version(output: str) -> str | None:
    m = re.search(r"v?(\d+\.\d+\.\d+)", output)
    return m.group(1) if m else None


def installed_version(tool: str) -> str | None:
    exe = shutil.which(tool, path=f"{BIN}{os.pathsep}{os.environ.get('PATH', '')}")
    if not exe:
        return None
    try:
        out = subprocess.run([exe, *VERSION_CMD[tool][1:]], capture_output=True, text=True, timeout=30)  # noqa: S603
    except (OSError, subprocess.TimeoutExpired):
        return None
    return parse_version(out.stdout + out.stderr)


def version_ok(have: str | None, want: str | None) -> bool:
    if have is None:
        return False
    if want in (None, "latest"):
        return True
    return have == want or have.startswith(want + ".")


# ---------------------------------------------------------------- downloads (official sources + checksums)
def resolve_latest(tool: str) -> str:
    repo = {"tflint": "terraform-linters/tflint", "kind": "kubernetes-sigs/kind", "helm": "helm/helm"}[tool]
    with urllib.request.urlopen(f"https://api.github.com/repos/{repo}/releases/latest", timeout=30) as r:  # noqa: S310
        return json.load(r)["tag_name"].lstrip("v")


def artifact(tool: str, version: str, os_: str, arch: str) -> tuple[str, str, str]:
    """(download URL, checksum URL, name of the file inside the checksum list or '' for single-hash files)."""
    if tool == "kubectl":
        base = f"https://dl.k8s.io/release/v{version}/bin/{os_}/{arch}/kubectl"
        return base, base + ".sha256", ""
    if tool == "kind":
        base = f"https://github.com/kubernetes-sigs/kind/releases/download/v{version}/kind-{os_}-{arch}"
        return base, base + ".sha256sum", ""
    if tool == "helm":
        f = f"helm-v{version}-{os_}-{arch}.tar.gz"
        return f"https://get.helm.sh/{f}", f"https://get.helm.sh/{f}.sha256sum", ""
    if tool == "terraform":
        f = f"terraform_{version}_{os_}_{arch}.zip"
        base = f"https://releases.hashicorp.com/terraform/{version}"
        return f"{base}/{f}", f"{base}/terraform_{version}_SHA256SUMS", f
    if tool == "tflint":
        f = f"tflint_{os_}_{arch}.zip"
        base = f"https://github.com/terraform-linters/tflint/releases/download/v{version}"
        return f"{base}/{f}", f"{base}/checksums.txt", f
    raise KeyError(tool)


def expected_sha256(checksum_text: str, filename: str) -> str:
    if not filename:  # single-hash file: "<hash>" or "<hash>  <name>"
        return checksum_text.split()[0].lower()
    for line in checksum_text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[-1].lstrip("*") == filename:
            return parts[0].lower()
    raise ValueError(f"{filename} not listed in checksum file")


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "sunn-platform-lab-prereqs"})
    with urllib.request.urlopen(req, timeout=300) as r:  # noqa: S310 - fixed official URLs above
        return r.read()


def extract(tool: str, blob: bytes, url: str) -> bytes:
    if url.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            return z.read(next(n for n in z.namelist() if Path(n).name == tool))
    if url.endswith(".tar.gz"):
        with tarfile.open(fileobj=io.BytesIO(blob)) as t:
            member = next(m for m in t.getmembers() if Path(m.name).name == tool and m.isfile())
            return t.extractfile(member).read()  # type: ignore[union-attr]
    return blob


def install(tool: str, version: str) -> Path:
    os_, arch = platform_id()
    if version == "latest":
        version = resolve_latest(tool)
    url, sum_url, name = artifact(tool, version, os_, arch)
    blob = fetch(url)
    want = expected_sha256(fetch(sum_url).decode(), name)
    got = hashlib.sha256(blob).hexdigest()
    if got != want:
        raise SystemExit(f"checksum mismatch for {url}: got {got}, want {want}. Refusing to install.")
    BIN.mkdir(exist_ok=True)
    dest = BIN / tool
    dest.write_bytes(extract(tool, blob, url))
    dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return dest


# ---------------------------------------------------------------- environment checks
def docker_status() -> str | None:
    """None if Docker is usable for kind, else a human explanation."""
    if not shutil.which("docker"):
        return "docker not installed"
    info = subprocess.run(["docker", "info", "--format", "{{json .MemTotal}}"],  # noqa: S607
                          capture_output=True, text=True, timeout=30)
    if info.returncode != 0:
        return "docker daemon not running (start Docker Desktop / colima / dockerd)"
    try:
        mem_gb = int(info.stdout.strip()) / 1024**3
    except ValueError:
        return None
    if mem_gb < MIN_DOCKER_MEM_GB:
        return f"docker has {mem_gb:.1f} GB memory; kind + the platform need >= {MIN_DOCKER_MEM_GB} GB"
    return None


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def check(tools: list[str], pins: dict[str, str]) -> list[Result]:
    results = []
    for tool in tools:
        want = pins.get(tool)
        have = installed_version(tool)
        note = CHECK_ONLY.get(tool, "") if have is None else ""
        if tool == "docker" and have:
            problem = docker_status()
            results.append(Result(tool, problem is None, have, None, problem or ""))
            continue
        results.append(Result(tool, version_ok(have, want), have, want, note))
    return results


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--profile", choices=sorted(PROFILES), default="lab")
    p.add_argument("--install", action="store_true", help="install missing/mismatched tools into ./.bin")
    p.add_argument("--skip-docker", action="store_true", help="don't require a running Docker (e.g. macOS CI)")
    a = p.parse_args(argv)

    pins = pinned_versions()
    tools = [t for t in PROFILES[a.profile] if not (a.skip_docker and t == "docker")]
    results = check(tools, pins)

    if a.install:
        for r in results:
            if not r.ok and r.tool not in CHECK_ONLY:
                print(f"installing {r.tool} {r.want} -> {BIN}/{r.tool}")
                install(r.tool, r.want or "latest")
        results = check(tools, pins)

    width = max(len(t) for t in tools)
    for r in results:
        mark = "✅" if r.ok else "❌"
        detail = f"have {r.have or '-'}" + (f", want {r.want}" if r.want and not r.ok else "")
        print(f"{mark} {r.tool:<{width}}  {detail}  {r.note}".rstrip())
    if a.profile in ("lab", "all") and not a.skip_docker:
        busy = [str(port) for port in LAB_PORTS if not port_free(port)]
        if busy:
            print(f"⚠️  ports in use (port-forwards may clash): {', '.join(busy)}")

    failed = [r for r in results if not r.ok]
    if failed:
        hint = "" if a.install else "  (run with --install, or `make prereqs-install`)"
        print(f"\n{len(failed)} prerequisite(s) missing{hint}")
        return 1
    print(f"\nall {a.profile} prerequisites OK" + (f"  (tools in {BIN}; `make` adds it to PATH)" if BIN.exists() else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
