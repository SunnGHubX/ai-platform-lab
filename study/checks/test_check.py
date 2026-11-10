"""Unit tests for the exercise checker itself (so a broken checker can't green-light an exercise)."""
from pathlib import Path

import pytest
import yaml

import check
from check import FAIL, PASS, SKIP, load_spec, run_check


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "main.tf").write_text('resource "aws_s3_bucket" "data" {}\nmoved {\n}\nmoved {\n}\n')
    return tmp_path


def test_file_check(repo):
    assert run_check({"name": "x", "file": "a/main.tf"}, root=repo).status == PASS
    assert run_check({"name": "x", "file": "a/*.tf"}, root=repo).status == PASS
    assert run_check({"name": "x", "file": "nope.tf"}, root=repo).status == FAIL


def test_grep_min_count(repo):
    ok = {"name": "x", "grep": {"path": "a/*.tf", "pattern": r"^\s*moved\s*\{", "min": 2}}
    too_many = {"name": "x", "grep": {"path": "a/*.tf", "pattern": r"^\s*moved\s*\{", "min": 3}}
    assert run_check(ok, root=repo).status == PASS
    result = run_check(too_many, root=repo)
    assert result.status == FAIL and "found 2, need 3" in result.detail


def test_grep_missing_file_fails(repo):
    assert run_check({"name": "x", "grep": {"path": "zzz/*.tf", "pattern": "a"}}, root=repo).status == FAIL


def test_absent(repo):
    assert run_check({"name": "x", "absent": {"path": "a/main.tf", "pattern": '"this"'}}, root=repo).status == PASS
    assert run_check({"name": "x", "absent": {"path": "a/main.tf", "pattern": '"data"'}}, root=repo).status == FAIL


def test_run_pass_fail_and_quick(repo):
    assert run_check({"name": "x", "run": "true"}, root=repo).status == PASS
    failed = run_check({"name": "x", "run": "echo boom; false"}, root=repo)
    assert failed.status == FAIL and "boom" in failed.detail
    assert run_check({"name": "x", "run": "false"}, root=repo, quick=True).status == SKIP


def test_missing_tool_skips_locally_but_fails_in_strict_mode(repo):
    c = {"name": "x", "run": "true", "needs": ["definitely-not-a-real-tool"]}
    assert run_check(c, root=repo).status == SKIP
    assert run_check(c, root=repo, strict=True).status == FAIL


def test_spec_is_well_formed():
    spec = load_spec()
    assert sorted(spec) == [f"{i:02d}" for i in range(1, len(spec) + 1)], "exercise ids must be consecutive"
    for ex_id, ex in spec.items():
        assert ex["title"] and ex["checks"], ex_id
        for c in ex["checks"]:
            kinds = [k for k in ("file", "grep", "absent", "run") if k in c]
            assert len(kinds) == 1, f"{ex_id}/{c.get('name')}: exactly one check type"
            assert c["name"], ex_id


def test_every_exercise_doc_exists():
    docs = Path(check.ROOT, "study", "exercises")
    for ex_id in load_spec():
        assert list(docs.glob(f"{ex_id}-*.md")), f"no study/exercises/{ex_id}-*.md"


def test_fresh_repo_has_no_exercise_completed():
    """Sanity: exercises start unsolved; if one passes on main, its checks are too weak."""
    spec = load_spec()
    for ex_id in spec:
        results = check.check_exercise(ex_id, spec, quick=True)
        assert any(r.status == FAIL for r in results), f"exercise {ex_id} already passes - tighten its checks"


def test_branch_name_resolves_to_exercise(capsys):
    assert check.main(["ex/99-nope"]) == 2
    assert check.main(["ex/13-drills", "--quick"]) == 1  # unsolved -> non-zero
    assert check.main(["ex/25-red-team", "--quick"]) == 1


def test_yaml_anchors_not_treated_as_exercises():
    raw = yaml.safe_load(check.SPEC.read_text())
    assert "x-commands" in raw and "x-commands" not in load_spec()


def _check(ex_id: str, name_fragment: str) -> dict:
    return next(c for c in load_spec()[ex_id]["checks"] if name_fragment in c["name"])


@pytest.mark.parametrize(
    ("line", "flagged"),
    [
        ("      - uses: hashicorp/setup-terraform@v3", True),
        ("      - uses: sigstore/cosign-installer@main", True),
        ("      - uses: hashicorp/setup-terraform@b9cd54a3c349d3f38e8881555d616ced269862dd # v3.1.2", False),
        ("      - uses: actions/checkout@v4", False),  # first-party allowed by the exercise
        ("      - uses: github/codeql-action/init@v3", False),
        ("      - uses: ./.github/actions/local", False),
    ],
)
def test_ex24_sha_pinning_regex(tmp_path, line, flagged):
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "x.yaml").write_text(f"jobs:\n  a:\n    steps:\n{line}\n")
    result = run_check(_check("24", "pinned"), root=tmp_path)
    assert (result.status == FAIL) is flagged


def test_ex18_secret_manifest_regex_ignores_externalsecret(tmp_path):
    (tmp_path / "platform" / "x").mkdir(parents=True)
    f = tmp_path / "platform" / "x" / "a.yaml"
    c = _check("18", "no Secret manifests")
    f.write_text("kind: ExternalSecret\n---\nkind: SecretStore\n")
    assert run_check(c, root=tmp_path).status == PASS
    f.write_text("apiVersion: v1\nkind: Secret\n")
    assert run_check(c, root=tmp_path).status == FAIL
