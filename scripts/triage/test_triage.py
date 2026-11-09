"""Offline tests for the triage analyzers: each failure class from the drills has a fixture,
plus 'healthy' fixtures that must produce no findings (false positives page people at 3am)."""
import json

import pytest

import triage
from triage import analyze, main


def pod(name="gw-1", ns="inference", labels=None, phase="Running", cs=None, conditions=None, limit="256Mi"):
    return {
        "metadata": {"name": name, "namespace": ns, "labels": labels or {"app.kubernetes.io/name": "gw"}},
        "spec": {"containers": [{"name": "app", "resources": {"limits": {"memory": limit}}}]},
        "status": {"phase": phase, "conditions": conditions or [], "containerStatuses": cs or []},
    }


def running(ready=True, **extra):
    return {"name": "app", "image": "img:1", "ready": ready, "restartCount": 0, "state": {"running": {}}, **extra}


def state(**kinds):
    return {k: {"items": v} if isinstance(v, list) else v for k, v in kinds.items()}


def ids(findings):
    return [f.id for f in findings]


# ---------------------------------------------------------------- healthy cluster: no noise
def test_healthy_cluster_has_no_findings():
    s = state(
        pods=[pod(cs=[running()])],
        services=[{"metadata": {"name": "gw", "namespace": "inference"},
                   "spec": {"selector": {"app.kubernetes.io/name": "gw"}}}],
        endpointslices=[{"metadata": {"name": "gw-x", "namespace": "inference",
                                      "labels": {"kubernetes.io/service-name": "gw"}},
                         "endpoints": [{"conditions": {"ready": True}}]}],
        networkpolicies=[{"metadata": {"name": "gw", "namespace": "inference"},
                          "spec": {"policyTypes": ["Ingress", "Egress"],
                                   "egress": [{"ports": [{"port": 8000}]}, {"ports": [{"port": 53, "protocol": "UDP"}]}]}}],
        scaledobjects=[{"metadata": {"name": "vllm", "namespace": "inference"},
                        "status": {"conditions": [{"type": "Ready", "status": "True"}]}}],
    )
    assert analyze(s) == []


def test_system_namespaces_are_ignored():
    s = state(pods=[pod(ns="kube-system", cs=[{**running(), "state": {"waiting": {"reason": "CrashLoopBackOff"}}}])])
    assert analyze(s) == []


# ---------------------------------------------------------------- pods
def test_oomkilled_reports_the_limit():
    cs = {**running(ready=False), "restartCount": 4,
          "state": {"waiting": {"reason": "CrashLoopBackOff"}},
          "lastState": {"terminated": {"reason": "OOMKilled", "exitCode": 137}}}
    [f] = analyze(state(pods=[pod(cs=[cs], limit="20Mi")]))
    assert f.id == "OOMKILLED" and "20Mi" in f.summary and f.severity == "critical"


def test_crashloop_without_oom():
    cs = {**running(ready=False), "state": {"waiting": {"reason": "CrashLoopBackOff"}},
          "lastState": {"terminated": {"reason": "Error", "exitCode": 1}}}
    assert ids(analyze(state(pods=[pod(cs=[cs])]))) == ["CRASHLOOP"]


@pytest.mark.parametrize("reason", ["ImagePullBackOff", "ErrImagePull", "ErrImageNeverPull"])
def test_image_pull(reason):
    cs = {**running(ready=False), "state": {"waiting": {"reason": reason, "message": "not found"}}}
    assert ids(analyze(state(pods=[pod(cs=[cs])]))) == ["IMAGE_PULL"]


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("0/1 nodes are available: 1 Insufficient nvidia.com/gpu.", "UNSCHEDULABLE_GPU"),
        ("0/3 nodes are available: 3 node(s) had untolerated taint {nvidia.com/gpu: true}.", "UNTOLERATED_TAINT"),
        ("0/1 nodes are available: 1 Insufficient memory.", "UNSCHEDULABLE"),
    ],
)
def test_pending_pods(message, expected):
    p = pod(phase="Pending", conditions=[{"type": "PodScheduled", "status": "False", "message": message}])
    assert ids(analyze(state(pods=[p]))) == [expected]


def test_probe_failing_needs_repeated_events():
    p = pod(cs=[running(ready=False)])
    ev = {"involvedObject": {"namespace": "inference", "name": "gw-1"}, "reason": "Unhealthy",
          "message": "Readiness probe failed: HTTP probe failed with statuscode: 404"}
    assert analyze(state(pods=[p], events=[{**ev, "count": 1}])) == []  # one blip at startup is normal
    [f] = analyze(state(pods=[p], events=[{**ev, "count": 5}]))
    assert f.id == "PROBE_FAILING" and "404" in f.evidence[0]


# ---------------------------------------------------------------- services
SVC = {"metadata": {"name": "vllm", "namespace": "inference"}, "spec": {"selector": {"app.kubernetes.io/name": "vllm"}}}


def test_service_selector_matches_nothing():
    [f] = analyze(state(services=[SVC], pods=[pod(labels={"app.kubernetes.io/name": "vllm-typo"}, cs=[running()])]))
    assert f.id == "SERVICE_NO_ENDPOINTS" and "selector" in f.summary


def test_service_pods_exist_but_not_ready():
    findings = analyze(state(services=[SVC], pods=[pod(labels={"app.kubernetes.io/name": "vllm"}, cs=[running(ready=False)])],
                             endpointslices=[{"metadata": {"name": "s", "namespace": "inference",
                                                           "labels": {"kubernetes.io/service-name": "vllm"}},
                                              "endpoints": [{"conditions": {"ready": False}}]}]))
    assert ids(findings) == ["SERVICE_NO_ENDPOINTS"] and "none are Ready" in findings[0].summary


def test_headless_and_selectorless_services_ignored():
    s = state(services=[{"metadata": {"name": "ext", "namespace": "inference"}, "spec": {"type": "ExternalName"}},
                        {"metadata": {"name": "manual", "namespace": "inference"}, "spec": {}}])
    assert analyze(s) == []


# ---------------------------------------------------------------- network policies
def test_egress_policy_without_dns():
    np_ = {"metadata": {"name": "gw", "namespace": "inference"},
           "spec": {"podSelector": {"matchLabels": {"app": "gw"}}, "policyTypes": ["Egress"],
                    "egress": [{"ports": [{"port": 8000}]}]}}
    assert ids(analyze(state(networkpolicies=[np_]))) == ["NETPOL_NO_DNS"]


def test_default_deny_egress_flags_dns():
    np_ = {"metadata": {"name": "deny", "namespace": "mlops"}, "spec": {"podSelector": {}, "policyTypes": ["Egress"]}}
    assert ids(analyze(state(networkpolicies=[np_]))) == ["NETPOL_NO_DNS"]


def test_ingress_only_policy_is_fine():
    np_ = {"metadata": {"name": "i", "namespace": "x"}, "spec": {"podSelector": {}, "policyTypes": ["Ingress"]}}
    assert analyze(state(networkpolicies=[np_])) == []


# ---------------------------------------------------------------- autoscaling + alerts
def test_scaledobject_not_ready():
    so = {"metadata": {"name": "vllm", "namespace": "inference"},
          "status": {"conditions": [{"type": "Ready", "status": "False", "message": "dial tcp: no such host"}]}}
    [f] = analyze(state(scaledobjects=[so]))
    assert f.id == "SCALEDOBJECT_NOT_READY" and "no such host" in f.evidence[0]


def test_hpa_at_max():
    hpa = {"metadata": {"name": "keda-hpa-vllm", "namespace": "inference"},
           "spec": {"maxReplicas": 4}, "status": {"currentReplicas": 4, "desiredReplicas": 4}}
    assert ids(analyze(state(hpa=[hpa]))) == ["HPA_AT_MAX"]


def test_firing_alerts_use_their_runbook_and_skip_watchdog():
    alerts = {"data": {"alerts": [
        {"state": "firing", "labels": {"alertname": "Watchdog"}},
        {"state": "pending", "labels": {"alertname": "InferenceLatencyFastBurn"}},
        {"state": "firing", "labels": {"alertname": "InferenceAvailabilityFastBurn", "severity": "page"},
         "annotations": {"summary": "burning", "runbook_url": "https://x/rb.md"}},
    ]}}
    [f] = analyze({"alerts": alerts})
    assert f.id == "ALERT_FIRING" and f.severity == "critical" and f.runbook == "https://x/rb.md"


# ---------------------------------------------------------------- ordering, report, CLI
def test_critical_sorted_before_warning():
    hpa = {"metadata": {"name": "h", "namespace": "a"}, "spec": {"maxReplicas": 1},
           "status": {"currentReplicas": 1, "desiredReplicas": 1}}
    so = {"metadata": {"name": "s", "namespace": "a"}, "status": {}}
    assert [f.severity for f in analyze(state(hpa=[hpa], scaledobjects=[so]))] == ["critical", "warning"]


def test_every_finding_id_has_a_runbook():
    for fid in ["OOMKILLED", "CRASHLOOP", "IMAGE_PULL", "UNSCHEDULABLE_GPU", "UNTOLERATED_TAINT", "UNSCHEDULABLE",
                "PROBE_FAILING", "SERVICE_NO_ENDPOINTS", "NETPOL_NO_DNS", "SCALEDOBJECT_NOT_READY", "HPA_AT_MAX"]:
        assert triage.RUNBOOKS[fid]


def test_cli_from_bundle_and_expect(tmp_path, capsys):
    raw = tmp_path / "raw"
    raw.mkdir()
    cs = {**running(ready=False), "state": {"waiting": {"reason": "ImagePullBackOff"}}}
    (raw / "pods.json").write_text(json.dumps({"items": [pod(cs=[cs])]}))
    summary = tmp_path / "summary.md"
    assert main(["--from-dir", str(tmp_path), "--expect", "IMAGE_PULL", "--summary", str(summary)]) == 0
    assert "IMAGE_PULL" in summary.read_text()
    assert json.loads((tmp_path / "findings.json").read_text())[0]["id"] == "IMAGE_PULL"
    assert main(["--from-dir", str(tmp_path), "--expect", "OOMKILLED"]) == 1


def test_report_for_clean_cluster():
    assert "No problems detected" in triage.report([])


def test_runbook_anchors_exist_in_troubleshooting_guide():
    import re
    from pathlib import Path

    doc = (Path(__file__).resolve().parents[2] / "docs" / "troubleshooting.md").read_text()
    anchors = {re.sub(r"[^a-z0-9 -]", "", h.lower()).strip().replace(" ", "-") for h in re.findall(r"^#+ (.+)$", doc, re.M)}
    for fid, url in triage.RUNBOOKS.items():
        if "troubleshooting.md#" in url:
            assert url.split("#")[1] in anchors, f"{fid}: dangling anchor {url}"
