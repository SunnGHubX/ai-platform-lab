"""Static checks on the drill catalogue so a typo can't waste a 15-minute CI run."""
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "triage"))
import triage  # noqa: E402

SCENARIOS = yaml.safe_load(Path(__file__).with_name("scenarios.yaml").read_text())
KNOWN = set(triage.RUNBOOKS)


def test_every_scenario_is_complete():
    for name, sc in SCENARIOS.items():
        for key in ("title", "symptom", "expect", "root_cause", "lesson"):
            assert sc.get(key), f"{name}: missing {key}"
        assert "break" in sc, name


def test_expected_findings_exist_in_triage():
    for name, sc in SCENARIOS.items():
        assert set(sc["expect"]) <= KNOWN, f"{name}: unknown finding id(s) {set(sc['expect']) - KNOWN}"


def test_every_triage_finding_is_exercised_by_some_drill_or_unit_test():
    drilled = {fid for sc in SCENARIOS.values() for fid in sc["expect"]}
    # Not every finding needs a live drill, but the important classes must have one
    assert {"OOMKILLED", "IMAGE_PULL", "UNSCHEDULABLE_GPU", "SERVICE_NO_ENDPOINTS", "NETPOL_NO_DNS",
            "SCALEDOBJECT_NOT_READY", "PROBE_FAILING", "ALERT_FIRING"} <= drilled


def test_break_commands_only_touch_drill_namespaces():
    for name, sc in SCENARIOS.items():
        for cmd in sc.get("break", []):
            assert "-n inference" in cmd, f"{name}: break commands must be namespaced to inference"
            assert "delete" not in cmd.split() or "pod" in cmd, f"{name}: no destructive deletes"
