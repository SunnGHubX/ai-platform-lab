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
    assert sorted(spec) == [f"{i:02d}" for i in range(1, 14)]
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


def test_yaml_anchors_not_treated_as_exercises():
    raw = yaml.safe_load(check.SPEC.read_text())
    assert "x-commands" in raw and "x-commands" not in load_spec()
