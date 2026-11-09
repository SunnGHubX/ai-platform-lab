#!/usr/bin/env bash
# End-to-end test of the platform on a throwaway kind cluster.
#
# Installs the SAME Helm chart versions and values that Argo CD uses (read from gitops/apps/*.yaml),
# applies the real Kustomize manifests, then runs tests/e2e/smoke_test.py against the live cluster.
#
#   ./tests/e2e/run.sh                 # local (needs docker, kind, kubectl, helm, python3)
#   KEEP_CLUSTER=true ./tests/e2e/run.sh   # leave the cluster up to poke around
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CLUSTER="${CLUSTER:-sunn-e2e}"
KEEP_CLUSTER="${KEEP_CLUSTER:-false}"
WORK="$(mktemp -d)"
PF_PIDS=()
cd "$ROOT"

group()    { if [ -n "${GITHUB_ACTIONS:-}" ]; then echo "::group::$*"; else echo; echo "==> $*"; fi; }
endgroup() { if [ -n "${GITHUB_ACTIONS:-}" ]; then echo "::endgroup::"; fi; }

# Chart version + inline values straight from the Argo CD Application, so e2e can't drift from GitOps.
app_field() { # app_field <app.yaml> <version|values>
  python3 - "$1" "$2" <<'PY'
import sys, yaml
app = yaml.safe_load(open(sys.argv[1]))
srcs = app["spec"].get("sources") or [app["spec"]["source"]]
chart = next(s for s in srcs if "chart" in s)
if sys.argv[2] == "version":
    print(chart["targetRevision"])
else:
    print(yaml.safe_dump(chart.get("helm", {}).get("valuesObject", {}) or {}))
PY
}

diagnostics() {
  group "diagnostics"
  kubectl get pods -A -o wide || true
  kubectl get events -A --sort-by=.lastTimestamp | tail -40 || true
  for ns in inference mlops monitoring keda observability; do
    for p in $(kubectl -n "$ns" get pods -o name 2>/dev/null); do
      echo "--- $ns/$p"; kubectl -n "$ns" logs "$p" --all-containers --tail=40 2>/dev/null || true
    done
  done
  # Anything that restarted: why it died (OOMKilled? probe?) and what it said before dying
  kubectl get pods -A -o json | python3 -c '
import json,sys
for p in json.load(sys.stdin)["items"]:
    for c in p["status"].get("containerStatuses", []):
        if c.get("restartCount", 0):
            print(p["metadata"]["namespace"], p["metadata"]["name"], c["name"], c["restartCount"], json.dumps(c.get("lastState", {})))
' | while read -r ns pod ctr n last; do
    echo "--- RESTARTED $ns/$pod/$ctr x$n lastState=$last"
    kubectl -n "$ns" logs "$pod" -c "$ctr" --previous --tail=30 2>/dev/null || true
  done
  kubectl -n inference describe scaledobject vllm || true
  kubectl -n observability get svc,endpoints -o wide || true
  for f in "$WORK"/pf-*.log; do [ -f "$f" ] && { echo "--- $f"; tail -20 "$f"; }; done
  kubectl -n inference get hpa -o wide || true
  endgroup
}

cleanup() {
  rc=$?
  for pid in "${PF_PIDS[@]:-}"; do [ -n "$pid" ] && { pkill -P "$pid" 2>/dev/null; kill "$pid" 2>/dev/null; } || true; done
  [ $rc -ne 0 ] && diagnostics
  if [ "$KEEP_CLUSTER" != "true" ]; then kind delete cluster --name "$CLUSTER" >/dev/null 2>&1 || true; fi
  rm -rf "$WORK"
  exit $rc
}
trap cleanup EXIT

port_forward() { # port_forward <ns> <svc> <local:remote>  - reconnects if the backing pod restarts
  ( while true; do kubectl -n "$1" port-forward --address 127.0.0.1 "svc/$2" "$3" >>"$WORK/pf-$2.log" 2>&1; sleep 1; done ) &
  PF_PIDS+=($!)
}

wait_port() { # wait_port <port> - fail fast with the port-forward log instead of a vague timeout later
  for _ in $(seq 1 30); do (echo > "/dev/tcp/127.0.0.1/$1") 2>/dev/null && return 0; sleep 2; done
  echo "port $1 never came up"; cat "$WORK"/pf-*.log; return 1
}

group "kind cluster"
kind create cluster --name "$CLUSTER" --config tests/e2e/kind.yaml --wait 120s
endgroup

group "build + load images (gateway from this commit, mock LLM)"
docker build -q -t inference-gateway:e2e services/inference-gateway
docker build -q -t mock-llm:e2e tests/e2e/mock_llm
kind load docker-image inference-gateway:e2e mock-llm:e2e --name "$CLUSTER"
endgroup

group "helm repos"
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null
helm repo add kedacore https://kedacore.github.io/charts >/dev/null
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts >/dev/null
helm repo update >/dev/null
endgroup

group "kube-prometheus-stack $(app_field gitops/apps/monitoring.yaml version) with platform/monitoring/values.yaml"
helm upgrade --install monitoring prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace --version "$(app_field gitops/apps/monitoring.yaml version)" \
  -f platform/monitoring/values.yaml -f tests/e2e/values-monitoring.yaml --wait --timeout 10m
endgroup

group "KEDA $(app_field gitops/apps/keda.yaml version) with values from gitops/apps/keda.yaml"
app_field gitops/apps/keda.yaml values > "$WORK/keda-values.yaml"
helm upgrade --install keda kedacore/keda -n keda --create-namespace \
  --version "$(app_field gitops/apps/keda.yaml version)" -f "$WORK/keda-values.yaml" --wait --timeout 5m
endgroup

group "OpenTelemetry Collector $(app_field gitops/apps/otel-collector.yaml version) with platform/otel/values.yaml"
helm upgrade --install otel-collector open-telemetry/opentelemetry-collector -n observability --create-namespace \
  --version "$(app_field gitops/apps/otel-collector.yaml version)" -f platform/otel/values.yaml --wait --timeout 5m
endgroup

group "platform manifests: slo, mlflow, inference (vllm->mock, gateway)"
kubectl apply -k platform/slo
kubectl create namespace mlops --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -k platform/mlflow
kubectl create namespace inference --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -k tests/e2e/kustomize/inference
kubectl -n inference rollout status deploy/vllm --timeout=3m
kubectl -n inference rollout status deploy/inference-gateway --timeout=3m
kubectl -n mlops rollout status deploy/mlflow --timeout=10m
endgroup

group "port-forwards"
port_forward inference inference-gateway 18080:80
port_forward monitoring kps-prometheus 19090:9090
kubectl -n mlops patch svc mlflow -p '{"spec":{"type":"NodePort","ports":[{"name":"http","port":5000,"nodePort":30500}]}}'
kubectl -n observability patch svc otel-collector-opentelemetry-collector \
  -p '{"spec":{"type":"NodePort","ports":[{"name":"otlp-http","port":4318,"nodePort":30318}]}}'
for p in 18080 19090 15000 14318; do wait_port "$p"; done
endgroup

group "smoke tests"
GATEWAY_URL=http://localhost:18080 PROM_URL=http://localhost:19090 \
MLFLOW_URL=http://127.0.0.1:15000 OTLP_URL=http://127.0.0.1:14318 API_KEY=e2e-test-key \
  python3 -m pytest tests/e2e/smoke_test.py -v -p no:cacheprovider -o log_cli=false --junitxml="${JUNIT_XML:-$WORK/junit.xml}"
endgroup
