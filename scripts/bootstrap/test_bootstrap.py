"""Unit tests for prereqs.py, aws_bootstrap.py and argo_status.py (no network, no AWS, no cluster)."""
import hashlib
import io
import json
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

import argo_status
import aws_bootstrap as ab
import prereqs

ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------- prereqs
def test_mise_pins_every_installable_tool():
    pins = prereqs.pinned_versions()
    for tool in ["terraform", "tflint", "kubectl", "helm", "kind"]:
        assert pins.get(tool), f"{tool} not pinned in mise.toml"


@pytest.mark.parametrize(
    ("output", "version"),
    [
        ("Client Version: v1.37.2\nKustomize Version: v5.8.1", "1.37.2"),
        ("v3.22.1+gd6c1a0e", "3.22.1"),
        ("Terraform v1.17.1\non linux_amd64", "1.17.1"),
        ("kind v0.33.0 go1.26.7 linux/amd64", "0.33.0"),
        ("TFLint version 0.59.1\n+ ruleset.terraform (0.13.0-bundled)", "0.59.1"),
        ("no version here", None),
    ],
)
def test_parse_version(output, version):
    assert prereqs.parse_version(output) == version


@pytest.mark.parametrize(("have", "want", "ok"), [
    ("1.17.1", "1.17.1", True), ("1.17.2", "1.17.1", False), ("3.12.7", "3.12", True),
    ("0.59.1", "latest", True), (None, "1.0.0", False)])
def test_version_ok(have, want, ok):
    assert prereqs.version_ok(have, want) is ok


@pytest.mark.parametrize("tool", ["kubectl", "kind", "helm", "terraform", "tflint"])
@pytest.mark.parametrize(("os_", "arch"), [("linux", "amd64"), ("darwin", "arm64")])
def test_artifact_urls_are_official_https_with_checksums(tool, os_, arch):
    url, sums, _ = prereqs.artifact(tool, "1.2.3", os_, arch)
    assert url.startswith("https://") and sums.startswith("https://")
    assert os_ in url and arch in url
    assert any(h in url for h in ("dl.k8s.io", "github.com/kubernetes-sigs", "get.helm.sh",
                                   "releases.hashicorp.com", "github.com/terraform-linters"))


def test_expected_sha256_formats():
    assert prereqs.expected_sha256("ABC123\n", "") == "abc123"
    assert prereqs.expected_sha256("abc  kind-linux-amd64\n", "") == "abc"
    listing = "111  terraform_1_darwin_arm64.zip\n222  terraform_1_linux_amd64.zip\n"
    assert prereqs.expected_sha256(listing, "terraform_1_linux_amd64.zip") == "222"
    with pytest.raises(ValueError):
        prereqs.expected_sha256(listing, "missing.zip")


def _zip_with(name: str, payload: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(name, payload)
    return buf.getvalue()


def _tgz_with(path: str, payload: bytes) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        info = tarfile.TarInfo(path)
        info.size = len(payload)
        t.addfile(info, io.BytesIO(payload))
    return buf.getvalue()


@pytest.mark.parametrize(("tool", "archive"), [
    ("terraform", lambda: _zip_with("terraform", b"#!tf")),
    ("helm", lambda: _tgz_with("linux-amd64/helm", b"#!helm")),
    ("kubectl", lambda: b"#!kubectl"),
])
def test_install_verifies_checksum_and_extracts(tmp_path, monkeypatch, tool, archive):
    blob = archive()
    digest = hashlib.sha256(blob).hexdigest()
    monkeypatch.setattr(prereqs, "BIN", tmp_path)
    monkeypatch.setattr(prereqs, "platform_id", lambda: ("linux", "amd64"))

    def fake_fetch(url):
        if "SHA256SUMS" in url or url.endswith(("checksums.txt",)):
            return f"{digest}  terraform_1.0.0_linux_amd64.zip\n".encode()
        if url.endswith((".sha256", ".sha256sum")):
            return f"{digest}\n".encode()
        return blob

    monkeypatch.setattr(prereqs, "fetch", fake_fetch)
    dest = prereqs.install(tool, "1.0.0")
    assert dest.read_bytes().startswith(b"#!") and dest.stat().st_mode & 0o111


def test_install_refuses_checksum_mismatch(tmp_path, monkeypatch):
    monkeypatch.setattr(prereqs, "BIN", tmp_path)
    monkeypatch.setattr(prereqs, "platform_id", lambda: ("linux", "amd64"))
    monkeypatch.setattr(prereqs, "fetch", lambda url: b"0" * 64 if url.endswith(".sha256") else b"tampered")
    with pytest.raises(SystemExit, match="checksum mismatch"):
        prereqs.install("kubectl", "1.0.0")
    assert not (tmp_path / "kubectl").exists()


# ---------------------------------------------------------------- aws_bootstrap
def test_bucket_name_matches_state_backend_module():
    module = (ROOT / "terraform/modules/state-backend/main.tf").read_text()
    assert '"${var.project}-tfstate-${data.aws_caller_identity.current.account_id}-${data.aws_region.current.region}"' in module
    assert ab.bucket_name("123456789012", "us-east-1") == "ai-platform-tfstate-123456789012-us-east-1"


def test_configure_env_text_replaces_placeholders_idempotently():
    backend = (ROOT / "terraform/envs/dev/backend.hcl").read_text()
    out = ab.configure_env_text(backend, "dev", "123456789012", "eu-west-1")
    assert 'bucket       = "ai-platform-tfstate-123456789012-eu-west-1"' in out
    assert 'region       = "eu-west-1"' in out and "111111111111" not in out
    assert ab.configure_env_text(out, "dev", "123456789012", "eu-west-1") == out


def test_configure_env_text_only_touches_its_own_env_placeholder():
    text = 'account_id = "111111111111"\nother = "222222222222"\n'
    out = ab.configure_env_text(text, "dev", "123456789012", "us-west-2")
    assert 'account_id = "123456789012"' in out and '"222222222222"' in out


def test_backend_config_uses_lockfile_on_real_aws_and_endpoints_on_moto():
    real = ab.backend_config("dev", "123456789012", "us-west-2", None)
    assert "-backend-config=use_lockfile=true" in real and not any("endpoints" in c for c in real)
    fake = ab.backend_config("dev", "123456789012", "us-west-2", "https://localhost:5000")
    assert "-backend-config=insecure=true" in fake
    assert any("endpoints" in c for c in fake) and "-backend-config=use_lockfile=true" not in fake
    assert "-backend-config=key=_global/bootstrap/dev/terraform.tfstate" in real


def test_overrides_are_valid_hcl_shapes():
    assert 'backend "local"' in ab.local_backend_override("dev") and "state/dev.tfstate" in ab.local_backend_override("dev")
    assert 'backend "s3" {}' in ab.s3_backend_override()
    assert 's3 = "http://x"' in ab.provider_override("http://x")


def test_overrides_and_local_state_are_gitignored():
    ignore = (ROOT / ".gitignore").read_text()
    for p in ["backend_override.tf", "provider_override.tf", "bootstrap/state/", ".bin/"]:
        assert p in ignore


def test_rejects_bad_account_id():
    with pytest.raises(SystemExit, match="12 digits"):
        ab.main(["--env", "dev", "--account-id", "123"])


def test_prod_apply_requires_explicit_flag():
    with pytest.raises(SystemExit, match="i-mean-prod"):
        ab.main(["--env", "prod", "--account-id", "333333333333", "--apply"])


def test_preflight_refuses_wrong_account(monkeypatch):
    monkeypatch.setattr(ab.shutil, "which", lambda t: f"/usr/bin/{t}")
    monkeypatch.setattr(ab.Runner, "aws", lambda self, *a: json.dumps({"Account": "999999999999", "Arn": "x"}))
    with pytest.raises(SystemExit, match="not 123456789012"):
        ab.main(["--env", "dev", "--account-id", "123456789012", "--skip-github"])


def test_dry_run_changes_nothing(monkeypatch, capsys):
    monkeypatch.setattr(ab.shutil, "which", lambda t: f"/usr/bin/{t}")
    monkeypatch.setattr(ab.Runner, "aws", lambda self, *a: json.dumps({"Account": "123456789012", "Arn": "x"})
                        if a[0] == "sts" else (_ for _ in ()).throw(ab.BootstrapError("404")))
    before = {p: p.read_text() for p in (ROOT / "terraform/envs/dev").glob("*")}
    assert ab.main(["--env", "dev", "--account-id", "123456789012", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "[dry-run] terraform" in out and "migrate-state" in out and "[dry-run] gh" not in out
    assert before == {p: p.read_text() for p in (ROOT / "terraform/envs/dev").glob("*")}
    assert not (ab.BOOT / "backend_override.tf").exists()


# ---------------------------------------------------------------- argo_status
def _apps(*states):
    return {"items": [{"metadata": {"name": f"a{i}"}, "status": {"sync": {"status": s}, "health": {"status": h}}}
                      for i, (s, h) in enumerate(states)]}


@pytest.mark.parametrize(("apps", "minimum", "rc"), [
    (_apps(("Synced", "Healthy"), ("Synced", "Healthy")), 2, 0),
    (_apps(("Synced", "Healthy"), ("OutOfSync", "Healthy")), 2, 1),
    (_apps(("Synced", "Healthy")), 2, 1),        # root app synced but children not created yet
    ({"items": []}, 1, 1),
])
def test_argo_status(apps, minimum, rc):
    proc = subprocess.run([sys.executable, str(Path(argo_status.__file__)), "--min", str(minimum)],
                          input=json.dumps(apps), capture_output=True, text=True)
    assert proc.returncode == rc


def test_tls_policy_is_on_by_default_and_only_disabled_for_the_emulator(monkeypatch, capsys):
    boot_vars = (ROOT / "terraform/envs/_global/bootstrap/variables.tf").read_text()
    module_vars = (ROOT / "terraform/modules/state-backend/variables.tf").read_text()
    for text in (boot_vars, module_vars):
        block = text[text.index('variable "enforce_tls_policy"'):]
        assert "default     = true" in block.split("}")[0]
    monkeypatch.setattr(ab.shutil, "which", lambda t: f"/usr/bin/{t}")
    monkeypatch.setattr(ab.Runner, "aws", lambda self, *a: json.dumps({"Account": "123456789012", "Arn": "x"})
                        if a[-3:] != () and "sts" in a else (_ for _ in ()).throw(ab.BootstrapError("404")))
    assert ab.main(["--env", "dev", "--account-id", "123456789012", "--dry-run", "--skip-github"]) == 0
    assert "enforce_tls_policy=false" not in capsys.readouterr().out
