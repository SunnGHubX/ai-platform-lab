#!/usr/bin/env python3
"""triage: collect a Kubernetes debug bundle and name the likely root cause.

    python3 scripts/triage/triage.py --out /tmp/bundle                      # live cluster (current context)
    python3 scripts/triage/triage.py --out /tmp/b --prom-url http://localhost:9090
    python3 scripts/triage/triage.py --from-dir /tmp/bundle                 # re-analyze a saved bundle offline
    python3 scripts/triage/triage.py --out /tmp/b --expect OOMKILLED        # exit 1 unless that finding is present

The bundle (raw JSON, logs incl. previous containers, describe output, report.md, findings.json) is what you
attach to an incident or upload as a CI artifact. Analyzers are pure functions over the collected JSON, so they
are unit-tested offline (test_triage.py) with no cluster.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

REPO = "https://github.com/SunnGHubX/sunn-platform-lab/blob/main"
SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}
SYSTEM_NAMESPACES = {"kube-system", "kube-public", "kube-node-lease", "local-path-storage"}

# Finding id -> where to go next. Keep in sync with docs/troubleshooting.md.
RUNBOOKS = {
    "OOMKILLED": f"{REPO}/docs/troubleshooting.md#oomkilled",
    "CRASHLOOP": f"{REPO}/docs/troubleshooting.md#crashloopbackoff",
    "IMAGE_PULL": f"{REPO}/docs/troubleshooting.md#image-pull-errors",
    "UNSCHEDULABLE_GPU": f"{REPO}/docs/runbooks/VLLMQueueBacklog.md",
    "UNTOLERATED_TAINT": f"{REPO}/docs/troubleshooting.md#pending-pods",
    "UNSCHEDULABLE": f"{REPO}/docs/troubleshooting.md#pending-pods",
    "PROBE_FAILING": f"{REPO}/docs/troubleshooting.md#failing-probes",
    "SERVICE_NO_ENDPOINTS": f"{REPO}/docs/troubleshooting.md#service-has-no-endpoints",
    "NETPOL_NO_DNS": f"{REPO}/docs/troubleshooting.md#networkpolicy-blocks-dns",
    "SCALEDOBJECT_NOT_READY": f"{REPO}/docs/runbooks/VLLMQueueBacklog.md",
    "HPA_AT_MAX": f"{REPO}/docs/runbooks/VLLMQueueBacklog.md",
    "ALERT_FIRING": f"{REPO}/docs/runbooks",
}

RESOURCES = ["pods", "deployments", "services", "endpointslices", "networkpolicies", "hpa", "scaledobjects", "events"]


@dataclass
class Finding:
    id: str
    severity: str
    resource: str
    summary: str
    evidence: list[str] = field(default_factory=list)
    runbook: str = ""

    def __post_init__(self) -> None:
        self.runbook = self.runbook or RUNBOOKS.get(self.id, "")


def _name(obj: dict) -> str:
    md = obj.get("metadata", {})
    return f"{md.get('namespace', '-')}/{md.get('name', '?')}"


def _items(state: dict, kind: str) -> list[dict]:
    return [o for o in state.get(kind, {}).get("items", [])
            if o.get("metadata", {}).get("namespace") not in SYSTEM_NAMESPACES]


def _events_for(state: dict, ns: str, name: str) -> list[dict]:
    return [e for e in state.get("events", {}).get("items", [])
            if e.get("involvedObject", {}).get("namespace") == ns and e.get("involvedObject", {}).get("name") == name]


# ---------------------------------------------------------------- analyzers (pure functions)
def analyze_pods(state: dict) -> list[Finding]:
    out: list[Finding] = []
    for pod in _items(state, "pods"):
        ref = f"pod/{_name(pod)}"
        status = pod.get("status", {})
        ns, name = pod["metadata"]["namespace"], pod["metadata"]["name"]

        if status.get("phase") == "Pending":
            cond = next((c for c in status.get("conditions", []) if c.get("type") == "PodScheduled"), {})
            msg = cond.get("message", "")
            if cond.get("status") == "False":
                if "nvidia.com/gpu" in msg and "Insufficient" in msg:
                    out.append(Finding("UNSCHEDULABLE_GPU", "critical", ref,
                                       "No node has a free nvidia.com/gpu", [msg]))
                elif "untolerated taint" in msg:
                    out.append(Finding("UNTOLERATED_TAINT", "critical", ref,
                                       "Pod does not tolerate the taints on available nodes", [msg]))
                else:
                    out.append(Finding("UNSCHEDULABLE", "critical", ref, "Pod cannot be scheduled", [msg]))

        for cs in status.get("containerStatuses", []):
            waiting = cs.get("state", {}).get("waiting", {})
            last = cs.get("lastState", {}).get("terminated", {})
            reason = waiting.get("reason", "")
            if last.get("reason") == "OOMKilled":
                limit = next((c.get("resources", {}).get("limits", {}).get("memory")
                              for c in pod.get("spec", {}).get("containers", []) if c.get("name") == cs["name"]), None)
                out.append(Finding("OOMKILLED", "critical", f"{ref}:{cs['name']}",
                                   f"Container killed for exceeding its memory limit ({limit or 'no limit set'})",
                                   [f"restarts={cs.get('restartCount', 0)}", f"exitCode={last.get('exitCode')}"]))
            elif reason in {"ImagePullBackOff", "ErrImagePull", "ErrImageNeverPull", "InvalidImageName"}:
                out.append(Finding("IMAGE_PULL", "critical", f"{ref}:{cs['name']}",
                                   f"Image cannot be pulled: {cs.get('image')}",
                                   [f"{reason}: {waiting.get('message', '')}"[:300]]))
            elif reason == "CrashLoopBackOff":
                out.append(Finding("CRASHLOOP", "critical", f"{ref}:{cs['name']}",
                                   "Container keeps crashing; read the previous container's logs",
                                   [f"restarts={cs.get('restartCount', 0)}",
                                    f"lastExit={last.get('reason', '?')}/{last.get('exitCode', '?')}"]))
            elif "running" in cs.get("state", {}) and not cs.get("ready"):
                unhealthy = [e for e in _events_for(state, ns, name) if e.get("reason") == "Unhealthy"]
                count = sum(e.get("count", 1) or 1 for e in unhealthy)
                if count >= 3:
                    out.append(Finding("PROBE_FAILING", "warning", f"{ref}:{cs['name']}",
                                       "Container is running but its probes keep failing",
                                       sorted({e.get("message", "")[:200] for e in unhealthy})[:3]))
    return out


def _pods_matching(state: dict, ns: str, selector: dict) -> list[dict]:
    return [p for p in _items(state, "pods")
            if p["metadata"]["namespace"] == ns
            and selector.items() <= (p["metadata"].get("labels") or {}).items()]


def analyze_services(state: dict) -> list[Finding]:
    out: list[Finding] = []
    slices = _items(state, "endpointslices")
    for svc in _items(state, "services"):
        spec = svc.get("spec", {})
        selector = spec.get("selector")
        if not selector or spec.get("type") == "ExternalName":
            continue
        ns, name = svc["metadata"]["namespace"], svc["metadata"]["name"]
        ready = [ep for s in slices
                 if s["metadata"]["namespace"] == ns
                 and s["metadata"].get("labels", {}).get("kubernetes.io/service-name") == name
                 for ep in s.get("endpoints") or []
                 if (ep.get("conditions") or {}).get("ready", True)]
        if ready:
            continue
        matching = _pods_matching(state, ns, selector)
        if not matching:
            out.append(Finding("SERVICE_NO_ENDPOINTS", "critical", f"service/{ns}/{name}",
                               "Service selector matches no pods (label/selector mismatch?)",
                               [f"selector={json.dumps(selector, sort_keys=True)}"]))
        else:
            out.append(Finding("SERVICE_NO_ENDPOINTS", "critical", f"service/{ns}/{name}",
                               f"{len(matching)} pod(s) match but none are Ready",
                               [f"selector={json.dumps(selector, sort_keys=True)}"]))
    return out


def _allows_dns(rule: dict) -> bool:
    ports = rule.get("ports")
    if not ports:  # no ports listed = all ports to the rule's peers
        return True
    return any(str(p.get("port")) in {"53", "dns", "dns-tcp"} for p in ports)


def analyze_networkpolicies(state: dict) -> list[Finding]:
    out: list[Finding] = []
    for np_ in _items(state, "networkpolicies"):
        spec = np_.get("spec", {})
        if "Egress" not in (spec.get("policyTypes") or []):
            continue
        egress = spec.get("egress") or []
        if not any(_allows_dns(r) for r in egress):
            out.append(Finding("NETPOL_NO_DNS", "critical", f"networkpolicy/{_name(np_)}",
                               "Egress is restricted but DNS (port 53) is not allowed; selected pods can't resolve names",
                               [f"podSelector={json.dumps(spec.get('podSelector', {}), sort_keys=True)}",
                                f"egress rules={len(egress)}"]))
    return out


def analyze_autoscaling(state: dict) -> list[Finding]:
    out: list[Finding] = []
    for so in _items(state, "scaledobjects"):
        conds = so.get("status", {}).get("conditions", [])
        ready = next((c for c in conds if c.get("type") == "Ready"), None)
        if not ready or ready.get("status") != "True":
            out.append(Finding("SCALEDOBJECT_NOT_READY", "critical", f"scaledobject/{_name(so)}",
                               "KEDA cannot evaluate this ScaledObject; autoscaling is off",
                               [(ready or {}).get("message", "no Ready condition")[:300]]))
    for hpa in _items(state, "hpa"):
        st, sp = hpa.get("status", {}), hpa.get("spec", {})
        if sp.get("maxReplicas") and st.get("currentReplicas", 0) >= sp["maxReplicas"] \
                and st.get("desiredReplicas", 0) >= sp["maxReplicas"]:
            out.append(Finding("HPA_AT_MAX", "warning", f"hpa/{_name(hpa)}",
                               f"Autoscaler pinned at maxReplicas={sp['maxReplicas']}; demand exceeds capacity",
                               [f"current={st.get('currentReplicas')} desired={st.get('desiredReplicas')}"]))
    return out


def analyze_alerts(state: dict) -> list[Finding]:
    out: list[Finding] = []
    for a in state.get("alerts", {}).get("data", {}).get("alerts", []):
        if a.get("state") != "firing" or a.get("labels", {}).get("alertname") in {"Watchdog", "InfoInhibitor"}:
            continue
        labels, ann = a.get("labels", {}), a.get("annotations", {})
        sev = "critical" if labels.get("severity") in {"page", "critical"} else "warning"
        out.append(Finding("ALERT_FIRING", sev, f"alert/{labels.get('alertname')}",
                           ann.get("summary", labels.get("alertname", "")),
                           [ann.get("description", "")[:300]], runbook=ann.get("runbook_url", "")))
    return out


ANALYZERS = [analyze_pods, analyze_services, analyze_networkpolicies, analyze_autoscaling, analyze_alerts]


def analyze(state: dict) -> list[Finding]:
    findings = [f for a in ANALYZERS for f in a(state)]
    return sorted(findings, key=lambda f: (SEVERITY_ORDER.get(f.severity, 9), f.id, f.resource))


# ---------------------------------------------------------------- collection (live cluster)
def kubectl_json(*args: str) -> dict:
    proc = subprocess.run(["kubectl", *args, "-o", "json"], capture_output=True, text=True, timeout=60)  # noqa: S603, S607
    if proc.returncode != 0:
        return {"items": [], "error": proc.stderr.strip()[:500]}
    return json.loads(proc.stdout)


def collect(out: Path, prom_url: str | None) -> dict:
    raw = out / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    state: dict = {}
    for res in RESOURCES:
        state[res] = kubectl_json("get", res, "-A")
        (raw / f"{res}.json").write_text(json.dumps(state[res], indent=1))
    if prom_url:
        try:
            with urllib.request.urlopen(f"{prom_url.rstrip('/')}/api/v1/alerts", timeout=10) as r:  # noqa: S310
                state["alerts"] = json.load(r)
        except Exception as e:  # noqa: BLE001 - triage must never crash on a missing dependency
            state["alerts"] = {"error": str(e)}
        (raw / "alerts.json").write_text(json.dumps(state["alerts"], indent=1))
    return state


def collect_details(out: Path, findings: list[Finding]) -> None:
    """Logs (current + previous) and `describe` for every pod a finding points at."""
    logs = out / "logs"
    logs.mkdir(exist_ok=True)
    for ref in sorted({f.resource.split(":")[0] for f in findings if f.resource.startswith("pod/")}):
        ns, name = ref.removeprefix("pod/").split("/", 1)
        for label, extra in (("describe", ["describe", "pod", name]), ("logs", ["logs", name, "--all-containers", "--tail=200"]),
                             ("previous", ["logs", name, "--all-containers", "--previous", "--tail=200"])):
            proc = subprocess.run(["kubectl", "-n", ns, *extra], capture_output=True, text=True, timeout=60)  # noqa: S603, S607
            (logs / f"{ns}__{name}.{label}.txt").write_text(proc.stdout or proc.stderr)


def load_bundle(path: Path) -> dict:
    raw = path / "raw"
    return {p.stem: json.loads(p.read_text()) for p in raw.glob("*.json")}


# ---------------------------------------------------------------- reporting
def report(findings: list[Finding]) -> str:
    if not findings:
        return "### Triage\n\n✅ No problems detected.\n"
    icon = {"critical": "🔴", "warning": "🟠", "info": "🔵"}
    lines = ["### Triage findings", "", "| | Finding | Resource | What it means | Evidence | Next step |",
             "|---|---|---|---|---|---|"]
    for f in findings:
        ev = "<br>".join(e.replace("|", "\\|") for e in f.evidence if e)[:400]
        nxt = f"[runbook]({f.runbook})" if f.runbook else ""
        lines.append(f"| {icon.get(f.severity, '')} | `{f.id}` | `{f.resource}` | {f.summary} | {ev} | {nxt} |")
    counts = Counter(f.severity for f in findings)
    lines += ["", f"**{counts.get('critical', 0)} critical, {counts.get('warning', 0)} warning**", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--out", type=Path, help="collect from the live cluster into this bundle directory")
    src.add_argument("--from-dir", type=Path, help="analyze a previously collected bundle")
    p.add_argument("--prom-url", help="Prometheus base URL to include firing alerts")
    p.add_argument("--expect", action="append", default=[], help="finding id that must be present (repeatable)")
    p.add_argument("--summary", type=Path, help="append the markdown report here (e.g. $GITHUB_STEP_SUMMARY)")
    a = p.parse_args(argv)

    if a.from_dir:
        bundle, state = a.from_dir, load_bundle(a.from_dir)
    else:
        bundle, state = a.out, collect(a.out, a.prom_url)
    findings = analyze(state)
    if a.out:
        collect_details(bundle, findings)
    md = report(findings)
    (bundle / "report.md").write_text(md)
    (bundle / "findings.json").write_text(json.dumps([asdict(f) for f in findings], indent=1))
    print(md)
    if a.summary:
        with a.summary.open("a") as fh:
            fh.write(md)

    missing = [e for e in a.expect if e not in {f.id for f in findings}]
    if missing:
        print(f"expected finding(s) not detected: {', '.join(missing)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
