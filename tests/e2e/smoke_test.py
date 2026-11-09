"""E2E smoke tests against a live kind cluster (see run.sh). Each test proves one platform promise."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GATEWAY = os.environ["GATEWAY_URL"]
PROM = os.environ["PROM_URL"]
MLFLOW = os.environ["MLFLOW_URL"]
OTLP = os.environ["OTLP_URL"]
KEY = os.environ["API_KEY"]


def http(method: str, url: str, body: dict | None = None, headers: dict | None = None) -> tuple[int, dict | str]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 - localhost port-forward
            raw = r.read().decode()
            code = r.status
    except urllib.error.HTTPError as e:
        raw, code = e.read().decode(), e.code
    try:
        return code, json.loads(raw)
    except json.JSONDecodeError:
        return code, raw


def chat(model: str = "mock", key: str | None = KEY) -> int:
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    code, _ = http("POST", f"{GATEWAY}/v1/chat/completions",
                   {"model": model, "messages": [{"role": "user", "content": "ping"}]}, headers)
    return code


def promql(query: str) -> list:
    _, body = http("GET", f"{PROM}/api/v1/query?query={urllib.parse.quote(query)}")
    return body["data"]["result"]


def eventually(fn, timeout: float = 180, every: float = 5, what: str = "condition"):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            last = fn()
            if last:
                return last
        except Exception as e:  # noqa: BLE001 - keep polling, report at the end
            last = e
        time.sleep(every)
    pytest.fail(f"timed out after {timeout}s waiting for {what}; last={last!r}")


def kubectl(*args: str) -> str:
    return subprocess.run(["kubectl", *args], check=True, capture_output=True, text=True).stdout.strip()


# ---------------------------------------------------------------- gateway (hardened manifest + NetworkPolicy)
def test_gateway_rejects_requests_without_api_key():
    assert chat(key=None) == 401


def test_gateway_proxies_to_model_server_through_networkpolicy():
    assert chat() == 200


def test_gateway_maps_engine_failure_to_502():
    assert chat(model="fail") == 502


def test_gateway_runs_as_non_root_with_read_only_fs():
    spec = json.loads(kubectl("-n", "inference", "get", "deploy", "inference-gateway", "-o", "json"))["spec"]
    pod = spec["template"]["spec"]
    assert pod["securityContext"]["runAsNonRoot"] is True
    assert pod["containers"][0]["securityContext"]["readOnlyRootFilesystem"] is True


# ---------------------------------------------------------------- observability + SLOs
def test_prometheus_scrapes_gateway_and_model_server():
    def targets_up():
        up = promql('up{namespace="inference"} == 1')
        services = {r["metric"].get("service") for r in up}
        return {"inference-gateway", "vllm"} <= services and services
    eventually(targets_up, what="inference-gateway and vllm scrape targets to be up")


def test_sli_metrics_reach_prometheus():
    for _ in range(10):
        chat()
    eventually(lambda: promql("sum(gateway_requests_total)"), what="gateway_requests_total in Prometheus")
    eventually(lambda: promql('gateway_request_duration_seconds_bucket{le="2.5"}'), what="latency histogram")


def test_slo_rules_are_loaded_and_evaluating():
    def rules_loaded():
        _, body = http("GET", f"{PROM}/api/v1/rules")
        names = {r["name"] for g in body["data"]["groups"] for r in g["rules"]}
        return {"InferenceAvailabilityFastBurn", "InferenceLatencyFastBurn", "VLLMQueueBacklog",
                "slo:gateway_errors:ratio_rate5m"} <= names
    eventually(rules_loaded, what="PrometheusRule from platform/slo to be loaded")
    for _ in range(5):
        chat(model="fail")
    eventually(lambda: promql("slo:gateway_errors:ratio_rate5m > 0"),
               what="error-ratio recording rule to see the injected 5xx")


def test_vllm_dashboard_shipped_to_grafana():
    cm = kubectl("-n", "inference", "get", "configmap", "vllm-grafana-dashboard", "-o", "jsonpath={.metadata.labels}")
    assert '"grafana_dashboard":"1"' in cm


# ---------------------------------------------------------------- labs actually work
def test_lab04_mlflow_train_and_register():
    subprocess.run([sys.executable, str(ROOT / "labs/04-mlflow/train.py"), "--tracking-uri", MLFLOW, "--runs", "2"],
                   check=True, timeout=600)
    from mlflow import MlflowClient

    version = MlflowClient(tracking_uri=MLFLOW).get_model_version_by_alias("iris-rf", "champion")
    assert version.name == "iris-rf"


def test_lab06_otel_metrics_flow_to_prometheus():
    import socket

    port = int(urllib.parse.urlparse(OTLP).port)
    eventually(lambda: socket.create_connection(("127.0.0.1", port), timeout=2).close() or True,
               timeout=60, what=f"OTLP port-forward on {port}")
    env = {**os.environ}
    script = (ROOT / "labs/06-opentelemetry/emit.py").read_text().replace('"http://localhost:4318"', f'"{OTLP.replace("localhost", "127.0.0.1")}"')
    subprocess.run([sys.executable, "-c", script], check=True, timeout=120, env=env)
    eventually(lambda: promql('{__name__=~"inference_requests.*"}'), timeout=180,
               what="OTLP metric re-exposed by the collector and scraped by Prometheus")


# ---------------------------------------------------------------- autoscaling on queue depth (last: it adds pods)
def test_keda_scaledobject_is_ready():
    def ready():
        conds = json.loads(kubectl("-n", "inference", "get", "scaledobject", "vllm", "-o", "jsonpath={.status.conditions}") or "[]")
        return any(c["type"] == "Ready" and c["status"] == "True" for c in conds)
    eventually(ready, what="ScaledObject vllm Ready")


def test_keda_scales_vllm_when_queue_backs_up():
    kubectl("-n", "inference", "set", "env", "deploy/vllm", "MOCK_WAITING=50")
    eventually(lambda: int(kubectl("-n", "inference", "get", "deploy", "vllm", "-o", "jsonpath={.spec.replicas}")) >= 2,
               timeout=300, every=10, what="KEDA to scale vllm above 1 replica on vllm:num_requests_waiting")
