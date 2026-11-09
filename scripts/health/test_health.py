from pathlib import Path

from check_links import broken_links
from version_drift import charts, images, latest_stable, status

ROOT = Path(__file__).resolve().parents[2]


def test_repo_has_no_broken_relative_links():
    assert broken_links(ROOT) == []


def test_link_checker_finds_broken_and_ignores_urls_anchors_and_code(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "ok.md").write_text("x")
    (tmp_path / "README.md").write_text(
        "[ok](docs/ok.md) [dir](docs) [anchor](#top) [web](https://example.com) [ok-anchor](docs/ok.md#x)\n"
        "[bad](docs/missing.md)\n```\n[in code](nope.md)\n```\n![img](missing.png)\n")
    assert broken_links(tmp_path) == ["README.md: broken link -> docs/missing.md"]


def test_status_buckets():
    assert status("1.2.3", "1.2.3") == "✅ current"
    assert status("1.2.3", "1.2.4") == "🩹 patch behind"
    assert status("1.2.3", "1.4.0") == "⬆️ minor behind"
    assert status("1.2.3", "2.0.0") == "⚠️ major behind"
    assert status("v0.33.0", "0.33.0") == "✅ current"
    assert status("26.08-py3", "26.10-py3") == "❔ unknown"


def test_latest_stable_ignores_prereleases():
    assert latest_stable(["1.0.0", "1.2.0-rc.1", "1.1.5", "garbage"]) == "1.1.5"


def test_inventory_reads_pins_from_the_repo():
    names = {r["name"] for r in charts()}
    assert {"kube-prometheus-stack", "keda", "opentelemetry-collector"} <= names
    assert {r["name"] for r in images()} == {"mlflow", "vllm"}
